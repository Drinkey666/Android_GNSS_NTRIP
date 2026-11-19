"""Build the two isolated translation units using the recorded MSVC replay link."""
from pathlib import Path
import os
import subprocess
import tempfile
import sys
from guard import sha

out=Path(__file__).resolve().parent
root=out.parents[1]
source_hashes={
    "ppp.c":("370a3eb2c406b54219c916e517b08060f17378c7b42f4f41dfc4a9576a248c4a",
             "25a68fe0044094d6b6a28025ae702a1fdb261429c6daee2dc7b8741fc8b3e141"),
    "rtkcmn.c":("9fe32f57ac4300b7d477a41c7862e2e878848c98d213cb078ef9eec344f89aff",
                "48f4e2ef67e5fd1ac31b80885018de7f27ff8625fc34ac993ea3eb782a2eb250"),
}
def materialize_sources(dest):
    (out/"temp").mkdir(exist_ok=True)
    dest.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out/"temp") as scratch:
        inputs=Path(scratch)/"core"
        inputs.mkdir()
        for name,(original,_) in source_hashes.items():
            src=root/"core"/name
            assert sha(src)==original, name
            (inputs/name).write_bytes(src.read_text(encoding="utf-8-sig").encode("utf8"))
        subprocess.run(["git","apply","--whitespace=nowarn",str(out/"step13_private.patch")],
                       cwd=scratch,check=True)
        for name,(_,expected) in source_hashes.items():
            target=dest/name
            if not target.exists():
                target.write_text((inputs/name).read_text(encoding="utf8"),encoding="utf8")
            assert sha(target)==expected, name

if "--check-patch" in sys.argv:
    (out/"temp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out/"temp") as check:
        materialize_sources(Path(check))
    print("Verified both reconstructed translation units.")
    raise SystemExit(0)
else:
    materialize_sources(out/"core")
script=(root/"build/build.cmd").read_text(encoding="utf-8-sig").splitlines()
lines=script[:2]
link=next(l for l in script if l.startswith("link ") and "ppp_ssr_replay.exe" in l)
for source in ("ppp","rtkcmn"):
    original=str(root/"core"/(source+".c"))
    obj=str(root/"build"/(source+".obj"))
    command=next(l for l in script if l.startswith("cl ") and '"'+original+'"' in l)
    private=str(out/(source+".obj"))
    lines.extend([command.replace(original,str(out/"core"/(source+".c"))).replace(obj,private),
                  "if errorlevel 1 exit /b 1"])
    link=link.replace(obj,private)
lines.append(link.replace(str(root/"bin/ppp_ssr_replay.exe"),str(out/"step13_probe.exe")))
cmd=out/"build_private.cmd"
cmd.write_text("\n".join(lines)+"\n",encoding="utf8")
(out/"temp").mkdir(exist_ok=True)
with (out/"build_private.log").open("wb") as log:
    subprocess.run(["cmd","/d","/c",str(cmd)],cwd=out,env=dict(os.environ,TMP=str(out/"temp"),TEMP=str(out/"temp")),
                   stdout=log,stderr=subprocess.STDOUT,check=True)
