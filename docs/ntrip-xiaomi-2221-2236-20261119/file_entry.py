"""Capture-specific independent file replay; run from any directory on this PC."""
import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
WORK = OUT / "file_build"
PRODUCTS = OUT / "products"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def substitute(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Unexpected source or build rule: " + old)
    return text.replace(old, new)


def build(align=False):
    WORK.mkdir(exist_ok=False)
    src = ROOT / "src/gnss_replay.c"
    original = src.read_text(encoding="utf-8-sig")
    s = substitute(original, "!args.stream_session || args.rinex_source", "args.rinex_source")
    s = substitute(s, "if(!pc_ssr_open_profile(", "if(args.stream_session && !pc_ssr_open_profile(")
    anchor = '    smartphone_ppp_log("pc-ntrip-replay", &opt);'
    guard = """
    if(!args.stream_session) {
        pc_ppp_files_t files = {0};
        const char *paths[] = {args.txt,args.nav,args.sp3,args.clk,args.bia,args.ionex,
            args.vmf0,args.vmf6,args.orog,args.atx};
        const char *report = getenv("WHU_FILE_PREFLIGHT_REPORT");
        FILE *fp;
        int ok;
        opt.sateph = EPHOPT_PREC;
        files.source = PC_SOURCE_TXT;
        for (int j = 0; j < PC_OUTPUT; ++j) {
            if (!paths[j] || strlen(paths[j]) >= sizeof(files.path[j])) goto done;
            strcpy(files.path[j], paths[j]);
        }
        if (!report || !(fp = fopen(report, "wb"))) goto done;
        ok = ppp_product_check_files(&files, &opt, 0, fp);
        fclose(fp);
        if (!ok) {fprintf(stderr,"FILE_PREFLIGHT_FAILED\\n"); goto done;}
    }
"""
    s = substitute(s, anchor, guard + anchor)
    # Require a valid satellite + observable + time OSB even when a particular
    # Bias-SINEX header omits its clock reference. Leave carrier ambiguities float.
    anchor = "    source_epoch=obs[0].time;"
    s = substitute(s, anchor, anchor + """
    if (!pc_ssr_active()) {
        memcpy(corrected, obs, sizeof(*obs) * nobs);
        for (i=0; i<nobs; ++i) for (f=0; f<NFREQ; ++f) {
            if (corrected[i].P[f] && codeosb_at(nav, source_epoch,
                    corrected[i].sat, corrected[i].code[f], NULL) != 1)
                corrected[i].P[f] = 0.0;
        }
        obs = corrected;
    }""")
    if align:
        with (OUT/"SSR/solution.csv").open() as source:
            first = next(row for row in csv.DictReader(source) if int(row["nobs"]) > 0)
        gate = """
    if (!pc_ssr_active() && timediff(source_epoch, gpst2time(%s, %s)) < -1e-6) {
        tow = time2gpst(source_epoch, &week);
        if (result_file) fprintf(result_file,"%%d,%%.9f,0,0,0,,,,,,,,,,0\\n",week,tow);
        perf->status_count[0]++;
        add_perf(perf, adapter_ms);
        return 1;
    }""" % (first["week"],first["tow"])
        s = substitute(s,anchor,anchor+gate)
    entry = WORK / src.name
    entry.write_text(s, encoding="utf8")
    (WORK/"entry.diff").write_text("".join(difflib.unified_diff(
        original.splitlines(True), s.splitlines(True), "formal/gnss_replay.c", "file/gnss_replay.c")), encoding="utf8")
    rules = (ROOT/"build/build.cmd").read_text().splitlines()
    compile_rule = next(line for line in rules if line.startswith("cl ") and str(src) in line)
    link = next(line for line in rules if line.startswith("link ") and str(ROOT/"bin/ppp_ssr_replay.exe") in line)
    obj = ROOT/"build/gnss_replay.obj"
    compile_rule = compile_rule.replace(str(src), str(entry)).replace(str(obj), str(WORK/obj.name))
    link = link.replace(str(obj),str(WORK/obj.name)).replace(str(ROOT/"bin/ppp_ssr_replay.exe"),str(WORK/"replay.exe"))
    batch = WORK/"build.cmd"
    batch.write_text("\n".join(rules[:2]+[compile_rule,"if errorlevel 1 exit /b 1",link,"exit /b %errorlevel%"])+"\n")
    with (WORK/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=ROOT,check=True,stdout=log,
                       stderr=subprocess.STDOUT,env=dict(os.environ,TMP=str(WORK),TEMP=str(WORK)))
    pins = {n:sha(n) for n in re.findall(r'"([^"]+\.obj)"',link)}
    pins.update({str(p):sha(p) for p in (src,entry,WORK/"replay.exe",ROOT/"bin/ppp_ssr_replay.exe")})
    (WORK/"sha256.json").write_text(json.dumps(pins,indent=2))


def run(name,sp3,clk,bia,nav,atx):
    dest = OUT/name
    dest.mkdir(exist_ok=False)
    receipt = json.loads((OUT/"SSR/replay.json").read_text())
    args = list(receipt["command"])
    args[0] = str(WORK/"replay.exe")
    for flag in ("--stream-session","--ssr-datum","--ssr-profile","--ssr-phase-osb","--stream-latency-ms","--ssr-diagnostic"):
        idx = args.index(flag)
        del args[idx:idx+2]
    for flag,filename in (("--result-file","solution.csv"),("--state-dump","solution.stat"),
                          ("--obs-dump","observations.csv"),("--trace","solution.trace")):
        args[args.index(flag)+1] = str(dest/filename)
    args[args.index("--atx")+1] = str(atx)
    for key,path in (("--nav",nav),("--sp3",sp3),("--clk",clk),("--bia",bia)):
        args.extend([key,str(path)])
    env = {k:v for k,v in os.environ.items() if not k.startswith(("RTK_PPP_","SSR_","PPP_CAUSAL_"))}
    env.update(RTK_PPP_IONEX_TIME="CORRECTED", WHU_FILE_PREFLIGHT_REPORT=str(dest/"preflight.log"))
    (dest/"command.json").write_text(json.dumps(dict(args=args,products={str(p):sha(p) for p in [sp3,clk,bia,nav,atx]},
        entry_sha256=sha(args[0]),ionex_time="CORRECTED",files_preloaded=True),indent=2))
    with (dest/"console.log").open("wb") as log:
        result=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    (dest/"returncode.json").write_text(json.dumps({"returncode":result.returncode}))
    result.check_returncode()


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--same-start", action="store_true",help="Diagnostic aligned to the first actual SSR filter call")
    for key in ["name","sp3","clk","bia","nav","atx"]:
        ap.add_argument("--"+key)
    args=ap.parse_args()
    if args.same_start:
        WORK=OUT/"aligned_file_build"
    if args.build:
        build(args.same_start)
    else:
        run(args.name,*[(PRODUCTS/getattr(args,k)).resolve(strict=True) for k in ("sp3","clk","bia","nav","atx")])
