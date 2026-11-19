"""Build a private diagnostic with an offline, time-bounded WHU code-bias substitution."""
import os,subprocess
from experiments import D,ROOT
w=D/'private_final'
w.mkdir()
def edit(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
src=(ROOT/'src/ntrip_ssr.cpp').read_text(encoding='utf-8-sig')
anchor='    int out=0;const char *whu_pending=nullptr;'
src=edit(src,anchor,anchor+"""
    const char *mode=std::getenv("FIELD_CASE");
    const bool file_all=mode && !strcmp(mode,"file_all");
    const bool file_gap=mode && !strcmp(mode,"file_gap");
    static nav_t *file_nav=nullptr;
    if ((file_all || file_gap) && !file_nav) {
        file_nav=(nav_t*)calloc(1,sizeof(nav_t));
        if(!file_nav || !getenv("FIELD_BIA") || !readdcb(getenv("FIELD_BIA"),file_nav,nullptr) || file_nav->nosb<=0)abort();
    }
    static FILE *audit=fopen("sat_gate.csv","wb");
    if(!audit)abort();
    int week;
    double tow=time2gpst(epoch,&week);
""")
s='        if(!usable(sat,epoch,&why)) {'
src=edit(src,s,"""
        bool live=usable(sat,epoch,&why);
        bool fill=file_gap && (why=="WHU_OSB_ESTIMATE_NOT_ADVANCING");
        bool file=file_all || fill;
        fprintf(audit,"%d,%.9f,%d,%s\\n",week,tow,sat,why.c_str());
        // The all-file comparison substitutes only on fully admitted live satellites
        // or when the advancement watchdog is the sole failed code test.
        bool eligible=live || ((file_all || file_gap) && why=="WHU_OSB_ESTIMATE_NOT_ADVANCING");
        if (eligible && !live) {
            for(int k=0;k<3;k++)if(!std::isfinite(s.deph[k]) ||
                !std::isfinite(s.ddeph[k]) || !std::isfinite(s.dclk[k]))eligible=false;
        }
        if(!eligible) {""")
anchor='        nav->ssr[sat-1]=s;'
src=edit(src,anchor,"""
        if(file) {
            for(int f=0;f<NFREQ;f++) {
                const int code=obs[i].code[f];
                if(code<=0 || code>MAXCODE)continue;
                double bias=0.0;
                // The stream mask is retained. The stale stream estimate is never applied.
                bool valid=s.cbias_valid[code-1] && codeosb_at(file_nav,epoch,sat,code,&bias)==1;
                if(live && valid && obs[i].P[f]!=0) {
                    static FILE *pairs=fopen("bias_pairs.csv","wb");
                    if(!pairs)abort();
                    fprintf(pairs,"%d,%.9f,%d,%d,%.6f\\n",week,tow,sat,code,s.cbias[code-1]+bias);
                }
                s.cbias_valid[code-1]=valid;
                if(valid)s.cbias[code-1]=(float)-bias;
            }
        }
"""+anchor)
entry=(ROOT/'src/gnss_replay.c').read_text(encoding='utf-8-sig')
(w/'entry.c').write_text(entry,encoding='utf8')
(w/'decoder.cpp').write_text(src,encoding='utf8')
rules=(ROOT/'build/build.cmd').read_text().splitlines()
cmds=rules[:2]
link=next(s for s in rules if s.startswith('link ') and str(ROOT/'bin/ppp_ssr_replay.exe') in s)
for old,new in [('gnss_replay.c','entry.c'),('ntrip_ssr.cpp','decoder.cpp')]:
    obj=ROOT/'build'/(old.rsplit('.',1)[0]+'.obj')
    orig=ROOT/'src'/old
    cmd=next(s for s in rules if s.startswith('cl ') and str(orig) in s)
    cmds.extend([cmd.replace(str(orig),str(w/new)).replace(str(obj),str(w/obj.name)),'if errorlevel 1 exit /b 1'])
    link=link.replace(str(obj),str(w/obj.name))
cmds.extend([link.replace(str(ROOT/'bin/ppp_ssr_replay.exe'),str(w/'replay.exe')),'exit /b %errorlevel%'])
batch=w/'build.cmd'
batch.write_text('\n'.join(cmds)+'\n')
with (w/'build.log').open('wb') as log:
    subprocess.run(['cmd','/d','/c',str(batch)],cwd=w,env=dict(os.environ,TEMP=str(w),TMP=str(w)),stdout=log,stderr=subprocess.STDOUT,check=True)
