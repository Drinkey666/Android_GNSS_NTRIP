"""Terrestrial-frame transformations and regional velocity sensitivities."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
MAS = math.pi / (180 * 3600 * 1000)

# NASA/NSIDC ICESat-2 Data Comparison Users' Guide R007, Appendix B.
# Position vector convention, ITRF2020 -> older frame, at epoch 2015.0.
# Parameter order Tx Ty Tz [mm], scale [ppb], Rx Ry Rz [mas],
# followed by rates per year in the same units.
HELMERT = {
    "ITRF97": ((6.5, -3.9, -77.9, 3.98, 0, 0, .36), (.1, -.6, -3.1, .12, 0, 0, .02)),
    "ITRF2008": ((.2, 1.0, 3.3, -.29, 0, 0, 0), (0, -.1, .1, .03, 0, 0, 0)),
    "ITRF2014": ((-1.4, -.9, 1.4, -.42, 0, 0, 0), (0, -.1, .2, 0, 0, 0, 0)),
}
# NGA-U-2023-02846 Table 2, G2139 -> G2296 in position vector convention.
NGA_G2139_TO_G2296 = (2.6, 5.4, -.9, .06, -.01, -.07, 0)
PMM20 = np.array([-.085, -.519, .753])
PMM20_ORB = np.array([.37, .35, .74])
PMM14 = np.array([-.085, -.531, .770])

SOURCES = {
    "WangShen_TableS4.txt": (
        "https://dataverse.harvard.edu/api/access/datafile/3644757",
        "66b849e1d9ff250d96a7f45fc5488cf403339b6e981b3a4b866c36c62a17dbd0"),
    "CCEA.final.vel": (
        "https://zenodo.org/records/11203896/files/CCEA.final.vel?download=1", None),
    "ITRF2020_GNSS.SSC.txt": (
        "https://datacenter.iers.org/products/reference-systems/terrestrial/itrf/itrf2020/ITRF2020_GNSS.SSC.txt",
        "16609ae9d6d5a9e2754f81ce3d617051bee218f04a9c682c96d61cba40354a88"),
}

@dataclass(frozen=True)
class Scenario:
    name: str
    frame: str
    epoch: float | None

SCENARIOS = [
    Scenario("original","ITRF2020",None),
    Scenario("CGCS2000_2000","ITRF97",2000.0),
    Scenario("ITRF2008_2000","ITRF2008",2000.0),
    *[Scenario(f"ITRF2014_{int(epoch)}","ITRF2014",epoch) for epoch in (2015.,2020.,2024.)],
    Scenario("ITRF2014_obs_G2139_proxy","ITRF2014",None),
    Scenario("WGS84_G2139_obs_NGA2024","G2139",None),
    Scenario("WGS84_G2296_obs_ITRF2020_proxy","ITRF2020",None),
]

def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()

def validated_sources(folder):
    hashes = {}
    for name, (_, expected) in SOURCES.items():
        p = folder / name
        digest = sha(p)
        if expected is not None:
            assert digest == expected, name
        else:
            assert hashlib.md5(p.read_bytes(),usedforsecurity=False).hexdigest() == "4a8c56b5f7dc6843bfc1e51a4e73b785"
        hashes[name] = digest
    return hashes

def rotation(lat,lon):
    s,c = math.sin(lat),math.cos(lat)
    sl,cl = math.sin(lon),math.cos(lon)
    return np.array([[-sl,cl,0],[-s*cl,-s*sl,c],[c*cl,c*sl,s]])

def ecef(lat,lon,h,grs80=False):
    f = 1.0/(298.257222101 if grs80 else 298.257223563)
    e2 = f*(2-f)
    n = 6378137 / math.sqrt(1-e2*math.sin(lat)**2)
    return np.array([(n+h)*math.cos(lat)*math.cos(lon),(n+h)*math.cos(lat)*math.sin(lon),
                     (n*(1-e2)+h)*math.sin(lat)])

def geodetic_angles(xyz):
    x,y,z = xyz
    p = math.hypot(x,y)
    f = 1./298.257223563
    e2 = f*(2-f)
    lat = math.atan2(z,p*(1-e2))
    for _ in range(8):
        n = 6378137/math.sqrt(1-e2*math.sin(lat)**2)
        lat = math.atan2(z+e2*n*math.sin(lat),p)
    return lat,math.atan2(y,x)

def matrix(parameters):
    x,y,z,s,rx,ry,rz = parameters
    return np.array([x,y,z])*1e-3, np.eye(3)*(1+s*1e-9) + MAS*np.array(
        [[0,-rz,ry],[rz,0,-rx],[-ry,rx,0]])

def helmert(frame, epoch):
    p,rate = HELMERT[frame]
    return matrix(np.array(p) + np.array(rate)*(epoch-2015.0))

def frame_velocity_to_2020(position, velocity, frame):
    # Subtract dT/dt and dM/dt times the ITRF2020 position, including scale rate.
    translation,transform = helmert(frame,2015.)
    cart20 = np.linalg.solve(transform,position-translation)
    t1,m1 = helmert(frame,2016.)
    tdot = t1-translation
    mdot = (m1-np.eye(3))-(transform-np.eye(3))
    return np.linalg.solve(transform,velocity-tdot-mdot@cart20)

def from_gpst(week,tow):
    # GPS-minus-UTC = 18 s on the sampled October/November 2026 dates.
    return datetime(1980,1,6,tzinfo=timezone.utc)+timedelta(weeks=week,seconds=tow-18.0)

def decimal_year(utc):
    start = datetime(utc.year,1,1,tzinfo=timezone.utc)
    end = datetime(utc.year+1,1,1,tzinfo=timezone.utc)
    return utc.year + (utc-start).total_seconds()/(end-start).total_seconds()

def origin_at_observation(lat,lon,h,obs_epoch,scenario,rate2020_mmy):
    raw_xyz = ecef(lat,lon,h,grs80=scenario.frame=="ITRF97")
    start_epoch = scenario.epoch if scenario.epoch is not None else obs_epoch
    if scenario.frame == "ITRF2020":
        return raw_xyz
    if scenario.frame == "G2139":
        # NGA reports no rates for this pair. Hold the 2024.0 table fixed as a
        # centimetre-scale check, with G2296 as an ITRF2020 proxy.
        t,m = matrix(NGA_G2139_TO_G2296)
        return t + (m @ raw_xyz)
    t,m = helmert(scenario.frame,start_epoch)
    start_xyz = np.linalg.solve(m,raw_xyz-t)
    return start_xyz + rate2020_mmy*(obs_epoch-start_epoch)*1e-3

@dataclass(frozen=True)
class Station:
    code: str
    lat: float
    lon: float
    enu: np.ndarray
    sigma: np.ndarray

def regional_stations(folder):
    wang,ccea = [],[]
    for line in (folder/"WangShen_TableS4.txt").read_text().splitlines():
        if not line.strip() or line.startswith(("Table","*")):
            continue
        name,lon,lat,e,_,es,n,_,ns,_ = line.split()
        lat,lon = map(math.radians,(float(lat),float(lon)))
        rot = rotation(lat,lon)
        site_velocity = frame_velocity_to_2020(ecef(lat,lon,0),rot.T @ np.array([float(e),float(n),0])*1e-3,"ITRF2008")
        wang.append(Station(name,lat,lon,rot @ site_velocity*1e3,np.array([float(es),float(ns),0])))
    for line in (folder/"CCEA.final.vel").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        lon,lat,e,n,_,_,es,ns,_,u,_,us,name = line.split()
        lat,lon = map(math.radians,(float(lat),float(lon)))
        rot = rotation(lat,lon)
        pos = ecef(lat,lon,0)
        geo14 = rot.T @ np.array([float(e),float(n),float(u)])*1e-3 + np.cross(PMM14*MAS,pos)
        geo20 = frame_velocity_to_2020(pos,geo14,"ITRF2014")
        ccea.append(Station(name,lat,lon,rot @ geo20*1e3,np.array([float(es),float(ns),float(us)])))
    assert len(wang) > 1000 and len(ccea) == 187, (len(wang),len(ccea))
    return wang,ccea

def distance_km(a,b,site):
    return float(np.linalg.norm(ecef(a,b,0)-ecef(*site,0))/1000)

def local_rates(stations,lat,lon,count=8):
    ordered = sorted([(distance_km(s.lat,s.lon,(lat,lon)),s) for s in stations],key=lambda pair:pair[0])
    selected = []
    ids = set()
    for dist,s in ordered:
        if s.code in ids:
            continue
        ids.add(s.code)
        selected.append((dist,s))
        if len(selected)==count:
            break
    assert len(selected)==count and selected[-1][0]<100.0
    distances = np.array([r[0] for r in selected])
    weights = 1/np.maximum(10.,distances)**2
    weights /= weights.sum()
    values = np.stack([s.enu for _,s in selected])
    sigmas = np.stack([s.sigma for _,s in selected])
    mu = weights @ values
    spread = np.sqrt(weights @ ((values-mu)**2+sigmas**2))
    return mu,spread,selected,weights

def models(wang,ccea,lat,lon):
    wh,ws,wrows,ww = local_rates(wang,lat,lon)
    ch,cs,crows,cw = local_rates(ccea,lat,lon)
    primary = np.r_[wh[:2],ch[2]]
    sigmas = np.r_[ws[:2],cs[2]]
    head = ecef(lat,lon,0)
    rot = rotation(lat,lon)
    rigid = (rot @ (np.cross(PMM20*MAS,head)*1e3+PMM20_ORB))[:2]
    # The PMM authors advise using only its horizontal output.
    return {"regional_S4_CCEA":(primary,sigmas),
            "regional_CCEA":(ch,cs),
            "rigid_Eurasia_CCEA_U":(np.r_[rigid,ch[2]],np.r_[.25,.26,cs[2]])}, (
                ("Wang_Shen_S4",wrows,ww),("CCEA_v2",crows,cw))

def igs_comparators(folder,anchor):
    stations = {"WUHN","KMNM","KUNM","LHAZ"}
    latest = {}
    lines = (folder/"ITRF2020_GNSS.SSC.txt").read_text(encoding="ascii").splitlines()
    for idx,line in enumerate(lines[:-1]):
        tokens = line.split()
        if "GNSS" not in tokens:
            continue
        k = tokens.index("GNSS")
        code = tokens[k+1]
        if code not in stations or len(tokens[k+2:])<6:
            continue
        pos = np.array(tokens[k+2:k+5],dtype=float)
        soln = int(tokens[k+8]) if len(tokens)>k+8 else 1
        vel_line = lines[idx+1].split()
        if vel_line[0] != tokens[0] or len(vel_line)!=7:
            continue
        if code in latest and latest[code]["solution"]>=soln:
            continue
        lat,lon = geodetic_angles(pos)
        R = rotation(lat,lon)
        ENU = R @ np.array(vel_line[1:4],dtype=float)*1000
        sigma = np.sqrt((R**2)@np.array(vel_line[4:7],dtype=float)**2)*1000
        latest[code] = dict(code=code,solution=soln, distance_km=distance_km(lat,lon,anchor),
                            velocity_E_mmy=ENU[0],velocity_N_mmy=ENU[1],velocity_U_mmy=ENU[2],
                            sigma_diag_E_mmy=sigma[0],sigma_diag_N_mmy=sigma[1],sigma_diag_U_mmy=sigma[2],
                            use="distant_crosscheck_only")
    assert latest.keys()==stations, latest.keys()
    return [latest[code] for code in sorted(latest)]

def self_check():
    pos = np.array([6378137.,0,0])
    shift,m = matrix((0,0,0,0,0,0,1))
    assert (m@pos-pos+shift)[1]>0
    assert np.allclose(rotation(0,0) @ [1,2,3],[2,3,1],rtol=0,atol=1e-12)
    for model in HELMERT:
        t,m = helmert(model,2026.9)
        assert np.allclose(np.linalg.solve(m,t+m@pos-t), pos,rtol=0,atol=1e-8)
    assert decimal_year(datetime(2026,1,1,tzinfo=timezone.utc))==2026.0
