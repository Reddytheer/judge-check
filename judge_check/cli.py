"""Command line: python -m judge_check evaluate ..."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .data import load_cases, load_rubric
from .evaluate import evaluate
from .judge import DEFAULT_MODEL, LLMJudge, ReplayGrader
from .report import render


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="judge-check", description="Decide which rubric criteria an LLM judge can grade on its own.")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate", help="grade the labeled set and write a run record plus an HTML report")
    e.add_argument("--cases", default="data/aml_triage_v1_1.json")
    e.add_argument("--rubric", default="rubric/aml_triage_v1.yaml")
    e.add_argument("--grader", choices=["llm", "draft"], default="draft",
                   help="llm: model judge via the Anthropic API. draft: replay first-pass draft labels (offline)")
    e.add_argument("--model", default=DEFAULT_MODEL)
    e.add_argument("--probes", action="store_true", help="run adversarial probes against the judge (llm grader only)")
    e.add_argument("--out", default="runs/latest")
    a = p.parse_args(argv)

    dataset = load_cases(a.cases)
    rubric = load_rubric(a.rubric)
    grader = LLMJudge(model=a.model) if a.grader == "llm" else ReplayGrader("draft_labels")
    run = evaluate(dataset, rubric, grader, run_probes=a.probes, progress=lambda s: print(s, file=sys.stderr))
    notes = {c["id"]: c.get("review_note", "") for c in dataset["items"]}
    for r in run["rows"]:
        r["review_note"] = notes.get(r["id"], "")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False))
    title = "judge-check: first-pass draft vs reviewed gold" if a.grader == "draft" else f"judge-check: {a.model}"
    (out / "report.html").write_text(render(run, title))
    auto = [c for c, d in run["decisions"].items() if d["status"] == "automate"]
    print(f"Automate: {', '.join(auto) or 'none'} | Human review: {', '.join(c for c in run['decisions'] if c not in auto)}")
    print(f"Wrote {out / 'run.json'} and {out / 'report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
