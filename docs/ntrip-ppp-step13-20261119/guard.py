"""Verify the Step 12 chain, official build and read-only controls before and after."""
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = OUT.parent / "brain_step12_adaptive_ppp"
PREVIOUS = {
    "REPORT.md": "596a52e5b94049de3e22692fc86550bccaf6972c9e9faae04638afc7ead4516c",
    "TERMINAL_TABLES.md": "8d8686130204d80874512eec215b6d60d25713637bc75be897f7648b9a7e4499",
    "verification.json": "923afb5444fc06d6f69786b86132f3fb7609a56dddb8253cc7cc7b425eb5c5f9",
}
def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))
def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
def verify(stage):
    assert stage in ("before", "after")
    v=read(OLD/"verification.json")
    assert sha(OLD/"input_guard_sha256.json")==v["private_guard_manifest_sha256"]
    assert sha(OLD/"local_dependency_guard.json")==v["local_dependency_guard_sha256"]
    inputs={**read(OLD/"input_guard_sha256.json"), **{str(OLD/n):h for n,h in PREVIOUS.items()}}
    official={str(ROOT/"bin"/n):h for n,h in read(ROOT/"validation/build.json")["binaries"].items()}
    deps=read(OLD/"local_dependency_guard.json")
    assert (len(inputs),len(official),len(deps))==(251,9,89)
    fixed={str(OLD/n):h for n,h in v["sha256"].items()}
    frames=OUT.parent/"brain_step12_reference_frame_audit"
    fixed[str(frames/"frame_offsets.csv")]=v["candidate_offsets_sha256"]
    extra_file=OUT/"local_dependency_guard.json"
    if stage=="before":
        assert not extra_file.exists() and not (OUT/"input_guard_sha256.json").exists()
        extras=list((OLD/"runs").glob("*/A[12]_*/solution.csv"))
        assert len(extras)==12
        extras.extend([ROOT/"tools/evaluate_solution.py",frames/"reeval_accuracy.csv",
                       OUT.parent/"whu_first_complete_20261114/saved_v1_evaluation/summary.json"])
        evidence={**fixed, **{str(p):sha(p) for p in extras}}
        save(extra_file,evidence)
        save(OUT/"input_guard_sha256.json",inputs)
    assert inputs==read(OUT/"input_guard_sha256.json")
    evidence=read(extra_file)
    sets=dict(official_binaries=official,extended_step12_inputs=inputs,production_dependencies=deps,
              controls_and_evaluation=evidence)
    result={}
    for label,items in sets.items():
        bad=[p for p,h in items.items() if not Path(p).is_file() or sha(p)!=h]
        result[label]=dict(count=len(items),failures=bad)
    save(OUT/("guard_"+stage+".json"),result)
    print(result,flush=True)
    if any(r["failures"] for r in result.values()): raise SystemExit(1)
if __name__=="__main__": verify(sys.argv[1])
