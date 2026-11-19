"""Verify the saved hashes without modifying a guard or any of its inputs."""
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = OUT.parent / "brain_step11_presmooth_cmd_iono"

def sha(p):
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def save(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

def verify(stage):
    b = read(ROOT / "validation/build.json")["binaries"]
    previous = read(OLD / "input_guard_sha256.json")
    guardfile = OUT / "input_guard_sha256.json"
    additional = [OLD / f for f in ("verification.json", "REPORT.md", "TERMINAL_TABLES.md")]
    if stage == "before":
        assert not guardfile.exists()
        guard = {**previous, **{str(p): sha(p) for p in additional}}
        save(guardfile, guard)
        deps = [ROOT / "validation/build.json", OLD / "input_guard_sha256.json", ROOT / "build/build.cmd"]
        deps += list((ROOT / "core").glob("*.[ch]")) + list((ROOT / "src").glob("*.[ch]")) + list((ROOT / "src").glob("*.cpp"))
        deps += [ROOT / "validation/brain_step5_east_and_m1v2/runs" / d.name / "Baseline" / "command.json" for d in (ROOT / "validation/brain_step5_east_and_m1v2/runs").iterdir() if (d / "Baseline/command.json").is_file()]
        import re
        link = next(l for l in (ROOT / "build/build.cmd").read_text().splitlines() if l.startswith("link ") and "ppp_ssr_replay.exe" in l)
        deps += [Path(p) for p in re.findall(r'"([^"]+\.obj)"',link)]
        save(OUT / "local_dependency_guard.json", {str(p):sha(p) for p in deps})
    guard = read(guardfile)
    deps = read(OUT / "local_dependency_guard.json")
    assert len(b) == 9 and len(previous) == 245 and len(guard) == 248
    sets = [({str(ROOT / "bin" / n):v for n,v in b.items()}, "binary"), (guard, "step11_extended"), (deps, "dependencies")]
    result = {}
    for items, label in sets:
        failures = []
        for p, h in items.items():
            if not Path(p).is_file() or sha(p) != h:
                failures.append(str(p))
        result[label] = dict(checked=len(items), failures=failures)
    save(OUT / ("guard_" + stage + ".json"), result)
    print(result, flush=True)
    if any(s["failures"] for s in result.values()):
        raise SystemExit(1)

if __name__ == "__main__":
    verify(sys.argv[1])
