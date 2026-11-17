"""Run isolated Step 11 (S1..S4) replays across 6 datasets with strict input/output guards."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STEP5 = OUT.parent / "brain_step5_east_and_m1v2"
STEP10 = OUT.parent / "brain_step10_decomp_and_observability"
DATASETS = ("1120_xiaomi", "1120_vivo", "1004_xiaomi", "1004_vivo", "1031_xiaomi_V1", "1031_xiaomi_V2")
CANDIDATES = ("S1_O1_robust", "S2_Q0_presmooth", "S3_presmooth_cmd", "S4_joint")
OUTPUTS = {
    "--result-file": "solution.csv",
    "--ssr-diagnostic": "corrections.csv",
    "--state-dump": "solution.stat",
    "--obs-dump": "observations.csv",
    "--trace": "solution.trace",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def rows(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def baseline(dataset: str) -> Path:
    return STEP5 / "runs" / dataset / "Baseline"


def args_for(dataset: str):
    return read(baseline(dataset) / "command.json")["args"].copy()


def build_guard():
    guard = read(STEP10 / "input_guard_sha256.json")
    for p in (STEP10 / "verification.json", STEP10 / "REPORT.md", STEP10 / "TERMINAL_TABLES.md"):
        guard[str(p)] = sha(p)
    for d in DATASETS:
        for name in ("solution.trace", "solution.stat"):
            p = baseline(d) / name
            guard[str(p)] = sha(p)
    return guard


def check_guard(guard):
    for p, exp in guard.items():
        actual = sha(Path(p))
        assert actual == exp, f"Guard mismatch on {p}: {actual} != {exp}"


def launch(job):
    d, case = job
    output = OUT / "runs" / d / case
    output.mkdir(parents=True)
    args = args_for(d)
    args[0] = str(OUT / "step11_probe.exe")
    for option, name in OUTPUTS.items():
        args[args.index(option) + 1] = str(output / name)
    assert "--reference" not in args and "--ru" not in args
    prefixes = ("RTK_PPP_", "NTRIP_PRIVATE_", "STEP", "WHU_EAST_PROBE", "AUDIT_")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(prefixes)}
    env.update(TEMP=str(output), TMP=str(output), STEP11_SCHEME=case)
    save(output / "command.json", dict(args=args, scheme=case, exe_sha256=sha(Path(args[0]))))
    with (output / "console.log").open("wb") as log:
        subprocess.run(args, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    data = rows(output / "solution.csv")
    base = rows(baseline(d) / "solution.csv")
    assert [(r["week"], r["tow"]) for r in data] == [(r["week"], r["tow"]) for r in base], (d, case)
    assert all(sha(output / f) == sha(baseline(d) / f) for f in ("observations.csv", "corrections.csv")), (d, case)
    q_match = [r["Q"] for r in data] == [r["Q"] for r in base]
    q6_new = [r for r in data if r["Q"] == "6"]
    q6_base = [r for r in base if r["Q"] == "6"]
    assert q6_new and q6_new[0]["week"] == q6_base[0]["week"] and q6_new[0]["tow"] == q6_base[0]["tow"], (d, case)
    print(f"{d:14s} {case:18s} epochs={len(data)} q6={len(q6_new)} same_Q={q_match}", flush=True)
    return (d, case, len(data), len(q6_new), q_match)


def main():
    guard = build_guard()
    check_guard(guard)
    save(OUT / "input_guard_sha256.json", guard)
    jobs = [(d, c) for c in CANDIDATES for d in DATASETS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(launch, jobs))
    check_guard(guard)
    print(f"Completed {len(results)} replays and verified {len(guard)} guard SHA-256s.")


if __name__ == "__main__":
    main()
