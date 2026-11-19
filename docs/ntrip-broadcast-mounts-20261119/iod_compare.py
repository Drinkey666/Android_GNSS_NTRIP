import csv,json,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
from ntrip_capture import crc24
from replay_session import validate_capture
root=Path(__file__).resolve().parent
cap=root/'pc_live_split'
m=validate_capture(cap)
streams=[(cap/name).read_bytes() for name in ('ssr.rtcm3','broadcast.rtcm3','bias.rtcm3')]
buf=[bytearray() for _ in streams]
known=set()
seen=defaultdict(set);matched=defaultdict(set);missing=defaultdict(set)
for row in csv.DictReader((cap/'arrivals.csv').open()):
 ch=int(row['channel'])
 if row['event']=='RESET':buf[ch].clear()
 if row['event']!='DATA' or ch==2:continue
 pos=int(row['offset']);n=int(row['length']);b=buf[ch];b.extend(streams[ch][pos:pos+n])
 while len(b)>=6:
  if b[0]!=211 or b[1]&252:del b[0];continue
  size=6+((b[1]&3)<<8)+b[2]
  if len(b)<size: break
  if crc24(b[:size-3])!=int.from_bytes(b[size-3:size],'big'):del b[0];continue
  bits=''.join(format(v,'08b') for v in b[3:size-3]);del b[:size]
  def field(i,n):return int(bits[i:i+n],2)
  typ=field(0,12)
  if ch==1 and typ in (1019,1045,1046,1042):
   if typ==1019: s,issue='G',field(48,8)
   elif typ==1042: s,issue='C',((field(54,17)*8+14)//720)%240
   else:s,issue='E',field(30,10)
   known.add((s,field(12,6),issue));continue
  if ch!=0 or typ not in (1060,1243,1261):continue
  sysname,ni,nj={1060:('G',8,0),1243:('E',10,0),1261:('C',10,8)}[typ]
  ns=field(62,6); stride=6+ni+nj+191
  assert 0<=len(bits)-68-ns*stride<=7
  for j in range(ns):
   at=68+j*stride;prn=field(at,6)
   issue=field(at+6+ni,nj) if nj else field(at+6,ni)
   k=(sysname,prn,issue)
   seen[sysname].add(k)
   (matched if k in known else missing)[sysname].add(k)
out={s:dict(whu_distinct_sat_issue=len(v),matched_at_least_once=len(matched[s]),never_matched=len(v-matched[s]),ever_missing_at_arrival=len(missing[s])) for s,v in seen.items()}
print(out)
(root/'iod_pairs.json').write_text(json.dumps(out,indent=2),encoding='utf8')
