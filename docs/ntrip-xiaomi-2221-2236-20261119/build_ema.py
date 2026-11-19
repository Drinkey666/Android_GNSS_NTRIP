"""Combine the frozen E41 EMA kernel and the independent, bounded code-product reader."""
from pathlib import Path
import os,subprocess
from experiments import D,ROOT
work=D/'ema_build';work.mkdir()
prior=D.parent/'brain_step13_adaptive_refine'
s=(prior/'core/ppp.c').read_text(encoding='utf-8-sig')
anchor='if (!s13_scheme || opt->ionoopt'
assert s.count(anchor)==1
s=s.replace(anchor,'if ((!s13_scheme && (!getenv("STEP13_SCHEME") || strcmp(getenv("STEP13_SCHEME"),"CONTROL_NO_R_CHANGE"))) || opt->ionoopt')
s=s.replace('        s13_weight(rtk,obs[0].time,nv,R,Pp);','        if(s13_scheme) s13_weight(rtk,obs[0].time,nv,R,Pp);')
(work/'ppp.c').write_text(s,encoding='utf8')
rules=(prior/'build_private.cmd').read_text().splitlines()
cmd=next(l for l in rules if l.startswith('cl ') and str(prior/'core/ppp.c') in l)
cmd=cmd.replace(str(prior/'core/ppp.c'),str(work/'ppp.c')).replace(str(prior/'ppp.obj'),str(work/'ppp.obj'))
link=next(l for l in rules if l.startswith('link '))
link=link.replace(str(prior/'ppp.obj'),str(work/'ppp.obj')).replace(str(ROOT/'build/ntrip_ssr.obj'),str(D/'private_final/ntrip_ssr.obj')).replace(str(prior/'step13_probe.exe'),str(work/'replay.exe'))
batch=work/'build.cmd';batch.write_text('\n'.join(rules[:2]+[cmd,'if errorlevel 1 exit /b 1',link,'exit /b %errorlevel%'])+'\n')
with (work/'build.log').open('wb') as log:subprocess.run(['cmd','/c',str(batch)],cwd=work,env=dict(os.environ,TMP=str(work),TEMP=str(work)),stdout=log,stderr=subprocess.STDOUT,check=True)
