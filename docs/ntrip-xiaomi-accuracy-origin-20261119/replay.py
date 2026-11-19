"""Replay the two saved sessions using the existing, instrumented formal fast branch."""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "xiaomi_2221_2236_20261119"
PROBE = HERE.parent / "xiaomi_1120_startup_admission_20261119/private/new.exe"
LABELS = ("2221", "2236")

def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def replay(label, startup=False):
    receipt = read(SOURCE / label / "SSR/replay.json")
    for name, sha in receipt["input_sha256"].items():
        assert digest(receipt["input_files"][name]) == sha
    args = receipt["command"].copy()
    assert digest(args[0]) == receipt["executable_sha256"]
    args[0] = str(HERE.parent / "brain_step9_spp_bootstrap_audit/step9_probe.exe" if startup else PROBE)
    assert "--ru" not in args and "--reference" not in args
    dst = HERE / (label+"_spp" if startup else label)
    dst.mkdir()
    for flag in ("--ssr-diagnostic", "--result-file", "--state-dump", "--obs-dump", "--trace"):
        i = args.index(flag) + 1
        args[i] = str(dst / Path(args[i]).name)
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(
        ("RTK_PPP_","STEP","FIELD_","XIAOMI_","NTRIP_PRIVATE_","AUDIT_","WHU_EAST_PROBE"))}
    env.update(TMP=str(dst), TEMP=str(dst), STEP5_SCHEME="Baseline")
    if startup:
        env["STEP9_AUDIT_FILE"] = str(dst / "observer.tsv")
    with (dst / "console.log").open("wb") as log:
        subprocess.run(args, cwd=dst, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)

if __name__ == "__main__":
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda label: replay(label, "--startup" in sys.argv[1:]), LABELS))
