"""trader CLI.

Usage (from repo root):
  PYTHONPATH=src python -m trader.cli arm
  PYTHONPATH=src python -m trader.cli run --feed synthetic --max-ticks 100
  PYTHONPATH=src python -m trader.cli status
  PYTHONPATH=src python -m trader.cli approve 1-spec
"""
import argparse
import json
import pathlib
import sys

from . import risk
from . import approvals
from .config import load_config


def cmd_arm(args):
    risk.arm()
    print("risk layer armed (in-process). Kill file:",
          load_config().risk.kill_file)


def cmd_run(args):
    from .loop import run
    run(feed=args.feed, address=args.address, interval=args.interval,
        max_ticks=args.max_ticks, bankroll=args.bankroll)


def cmd_status(args):
    p = pathlib.Path("state/ticks.jsonl")
    if not p.exists():
        print("no ticks logged yet")
        return
    lines = p.read_text().strip().split("\n")
    last = json.loads(lines[-1])
    print(f"ticks: {len(lines)}")
    print("ledger:", json.dumps(last["ledger"], indent=2))
    print("last decision:", json.dumps(last.get("decision"), indent=2))


def cmd_review(args):
    p = pathlib.Path("state/ticks.jsonl")
    if not p.exists():
        print("no ticks logged yet")
        return
    ledgers = [json.loads(l)["ledger"] for l in p.read_text().strip().split("\n") if l.strip()]
    if not ledgers:
        print("no ticks logged yet")
        return
    first, last = ledgers[0], ledgers[-1]
    print(f"ticks: {len(ledgers)}")
    print(f"bankroll: ${first['bankroll']} -> ${last['bankroll']}")
    print(f"realized pnl: ${last['realized_pnl']}")
    print(f"fills: {last['fills']}  max dd: {last['drawdown_pct']}%")


def cmd_approve(args):
    if args.gate not in approvals.GATES:
        print(f"unknown gate. valid: {approvals.GATES}")
        sys.exit(1)
    p = pathlib.Path("state/approvals.json")
    data = json.loads(p.read_text()) if p.exists() else {}
    if args.gate == "6-ship":
        print("REFUSED: gate 6-ship (live) cannot be approved via CLI. "
              "Live deployment requires explicit human sign-off outside this tool.")
        sys.exit(1)
    data[args.gate] = True
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))
    print(f"gate {args.gate} approved. all approved: {approvals.all_approved()}")


def main():
    ap = argparse.ArgumentParser(prog="trader")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("arm", help="arm the risk layer (in-process)")

    r = sub.add_parser("run", help="run the paper loop")
    r.add_argument("--feed", default="synthetic", choices=["synthetic", "base"])
    r.add_argument("--address", default=None, help="Base token address (with --feed base)")
    r.add_argument("--interval", type=int, default=5)
    r.add_argument("--max-ticks", type=int, default=None)
    r.add_argument("--bankroll", type=float, default=50.0)

    sub.add_parser("status", help="show last tick ledger")
    sub.add_parser("review", help="summarize the paper soak")
    a = sub.add_parser("approve", help="approve a gate (never 6-ship via CLI)")
    a.add_argument("gate", help="gate name, e.g. 1-spec")

    args = ap.parse_args()
    {"arm": cmd_arm, "run": cmd_run, "status": cmd_status,
     "review": cmd_review, "approve": cmd_approve}[args.cmd](args)


if __name__ == "__main__":
    main()
