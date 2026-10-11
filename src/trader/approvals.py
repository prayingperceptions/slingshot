import json, pathlib

GATES = ["1-spec", "2-architecture", "3-plan", "4-build", "5-review", "6-ship"]

def load_approvals(path="state/approvals.json") -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())

def is_approved(gate: str, path="state/approvals.json") -> bool:
    return load_approvals(path).get(gate, False) is True

def all_approved(path="state/approvals.json") -> bool:
    approvals = load_approvals(path)
    return all(approvals.get(g, False) for g in GATES)

def require_all_approved():
    if not all_approved():
        raise SystemExit("Live mode refused: not all 6 gates approved in state/approvals.json")
