"""Replay the saved formal baseline inputs and assert exact solution parity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STEP6 = OUT.parent / "brain_step6_m1v3_targeted"
STEP8 = OUT.parent / "brain_step8_isb_rcb_seed"
DATASETS = ("1120_xiaomi", "1004_vivo", "1004_xiaomi", "1031_xiaomi_V2", "1120_vivo", "1031_xiaomi_V1")
OUTPUTS = {"--result-file": "solution.csv", "--ssr-diagnostic": "corrections.csv",
           "--state-dump": "solution.stat", "--obs-dump": "observations.csv",
           "--trace": "solution.trace"}
EXACT_FILES = ("observations.csv", "corrections.csv", "solution.stat")

def baseline(dataset):
    return OUT.parent / "brain_step5_east_and_m1v2" / "runs" / dataset / "Baseline"

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def args_for(dataset):
    return read(baseline(dataset) / "command.json")["args"]

def guard():
    inherited = read(STEP8 / "input_guard_sha256.json")
    if len(inherited) != 223:
        raise ValueError("Step 8 guard count differs")
    for name, expected in inherited.items():
        if sha(Path(name)) != expected:
            raise ValueError(f"Changed Step 8 dependency: {name}")
    binaries = read(ROOT / "validation/build.json")["binaries"]
    if len(binaries) != 9:
        raise ValueError("Formal build manifest count differs")
    for name, expected in binaries.items():
        if sha(ROOT / "bin" / name) != expected:
            raise ValueError(f"Changed formal binary: {name}")
    android = Path("E:/android/test/PPP_NTRIP/app/src/main/cpp/ppp_live/rtklib")
    manifest = android / "ntrip_profile.sha256"
    records = [line.split() for line in manifest.read_text().splitlines() if line.strip()]
    if len(records) != 33:
        raise ValueError("Shared manifest count differs")
    for expected, name in records:
        for source in (ROOT / "core" / name, android / name):
            data = source.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").rstrip("\r\n")
            if hashlib.sha256(data.encode()).hexdigest() != expected:
                raise ValueError(f"Changed shared source: {source}")
    paths = [manifest, ROOT / "validation/build.json", STEP6 / "pre_q6_init.csv"]
    paths.extend(ROOT / "bin" / name for name in binaries)
    paths.extend(path for directory in ("core", "src") for path in (ROOT / directory).rglob("*") if path.is_file())
    for dataset in DATASETS:
        paths.extend(baseline(dataset) / name for name in ("command.json", *OUTPUTS.values()))
    snapshot = {**inherited, **{str(path): sha(path) for path in paths}}
    return snapshot

def validate(dataset, output):
    original = baseline(dataset)
    expected, found = rows(original / "solution.csv"), rows(output / "solution.csv")
    assert expected and len(expected) == len(found), (dataset, len(expected), len(found))
    for a, b in zip(expected, found, strict=True):
        assert a.keys() == b.keys(), dataset
        bad = {k: (a[k], b[k]) for k in a if k != "processing_ms" and a[k] != b[k]}
        assert not bad, (dataset, b["week"], b["tow"], bad)
    exact = {file: sha(output / file) for file in EXACT_FILES}
    assert all(sha(original / file) == h for file, h in exact.items()), (dataset, exact)
    q6 = [row for row in found if row["Q"] == "6"]
    assert q6, dataset
    return dict(epochs=len(found), q6=len(q6), first_q6_week=int(q6[0]["week"]),
                first_q6_tow=float(q6[0]["tow"]), solution_fields_equal_except_processing_ms=True,
                exact_file_sha256=exact)

def launch(dataset):
    output = OUT / "runs" / dataset
    output.mkdir(parents=True)
    args = args_for(dataset)
    args[0] = str(OUT / "step9_probe.exe")
    for option, name in OUTPUTS.items():
        args[args.index(option) + 1] = str(output / name)
    assert not set(args).intersection(("--reference", "--ru"))
    prefixes = ("RTK_PPP_", "NTRIP_PRIVATE_", "STEP", "WHU_EAST_PROBE", "AUDIT_")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(prefixes)}
    env.update(TEMP=str(output), TMP=str(output), STEP9_AUDIT_FILE=str(output / "observer.tsv"))
    save(output / "command.json", dict(args=args, exe_sha256=sha(Path(args[0]))))
    with (output / "console.log").open("wb") as log:
        subprocess.run(args, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    evidence = validate(dataset, output)
    assert (output / "observer.tsv").stat().st_size > 0
    print(f"{dataset}: {evidence['epochs']} epochs, {evidence['q6']} Q6, exact baseline parity", flush=True)
    return dataset, evidence

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    opts = parser.parse_args()
    snapshot = guard()
    save(OUT / "input_guard_sha256.json", snapshot)
    with ThreadPoolExecutor(max_workers=opts.workers) as pool:
        evidence = dict(pool.map(launch, DATASETS))
    final = guard()
    assert final == snapshot, "Formal source, binary, old input or results changed"
    save(OUT / "replay_verification.json", dict(guard_counts=dict(previous=223, binaries=9, shared=33,
         total=len(snapshot)), datasets=evidence))

if __name__ == "__main__":
    main()
