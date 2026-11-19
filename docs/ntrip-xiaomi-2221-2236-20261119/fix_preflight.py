"""Correct the clock header reader for a blank program field, then replay the unchanged products."""
import concurrent.futures,difflib,importlib.util,os,subprocess
from experiments import D,ROOT
work=D/'file_check_build'
prior=D.parent/'vivo_1852_product_comparison_20261119'
def build():
    work.mkdir()
    orig=ROOT/'core/ppp_product_check.c';s=orig.read_text(encoding='utf-8-sig')
    old='char line[1024],sys[32],program[128],file[128],next[128];'
    assert s.count(old)==1
    t=s.replace(old,'char line[1024],field[41],file[128],next[128];')
    old='if(strstr(line,"SYS / PCVS APPLIED") &&\n           sscanf(line,"%31s %127s %127s",sys,program,file)==3) {'
    assert t.count(old)==1
    t=t.replace(old,'''if(strlen(line)>=60 && strstr(line+60,"SYS / PCVS APPLIED")) {
            /* RINEX CLK places the antenna model in columns 21--60. */
            memcpy(field,line+20,40);
            field[40]='\\0';
            if(sscanf(field,"%127s",file)!=1)continue;''')
    src=work/orig.name;src.write_text(t,encoding='utf8')
    (D/'clock_header.patch').write_text(''.join(difflib.unified_diff(s.splitlines(True),t.splitlines(True),'a/core/ppp_product_check.c','b/core/ppp_product_check.c',n=2)),encoding='utf8')
    rules=(ROOT/'build/build.cmd').read_text().splitlines()
    obj=ROOT/'build/ppp_product_check.obj'
    cmd=next(l for l in rules if l.startswith('cl ') and str(orig) in l)
    cmds=rules[:2]+[cmd.replace(str(orig),str(src)).replace(str(obj),str(work/obj.name)),'if errorlevel 1 exit /b 1']
    for label in ('standard','2221','2236'):
        oldwork=prior/'file_build' if label=='standard' else D/label/'file_aligned_build'
        dest=work/label;dest.mkdir()
        link=next(l for l in (oldwork/'build.cmd').read_text().splitlines() if l.startswith('link '))
        cmds += [link.replace(str(obj),str(work/obj.name)).replace(str(oldwork/'replay.exe'),str(dest/'replay.exe')),'if errorlevel 1 exit /b 1']
    batch=work/'build.cmd';batch.write_text('\n'.join(cmds)+'\n')
    with (work/'build.log').open('wb') as log:subprocess.run(['cmd','/c',str(batch)],cwd=work,env=dict(os.environ,TMP=str(work),TEMP=str(work)),stdout=log,stderr=subprocess.STDOUT,check=True)
def run(arg):
    label,align=arg
    spec=importlib.util.spec_from_file_location('old',D/'file_entry.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.OUT=D/label;m.WORK=work/(label if align else 'standard')
    p=D/'products';pref='pride_WUM0MGXRTS_20263230000_01D_'
    m.run('FILE_checked_same_start' if align else 'FILE_checked',*(p/(pref+t) for t in ['05M_ORB.SP3','05S_CLK.CLK','05M_OSB.BIA']),p/'BRDC00WRD_S_20263230000_01D_MN.rnx',p/'igs20.atx')
if __name__=='__main__':
    build()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:list(pool.map(run,[(s,a) for s in ['2221','2236'] for a in (False,True)]))
