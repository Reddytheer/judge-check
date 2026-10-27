"""The evaluation pipeline: code checks -> grader -> metrics -> probes -> decisions."""
from __future__ import annotations

from datetime import datetime, timezone

from .checks import run_checks
from .data import fingerprint
from .judge import ReplayGrader
from .metrics import criterion_stats, decide
from .probes import PROBES, apply_probe


def evaluate(dataset: dict, rubric: dict, grader, run_probes: bool = False, progress=None) -> dict:
    criteria = [c["id"] for c in rubric["criteria"]]
    cases = dataset["items"]
    rows = []
    for i, case in enumerate(cases):
        chk = run_checks(case)
        judged = grader.grade(case, rubric, chk.flags, chk.hard_fails)
        combined = {c: ("F" if c in chk.hard_fails else judged[c]["verdict"]) for c in criteria}
        rows.append({
            "id": case["id"],
            "gold": case["gold_labels"],
            "judge": {c: judged[c]["verdict"] for c in criteria},
            "judge_reasons": {c: judged[c]["reason"] for c in criteria},
            "code_fails": chk.hard_fails,
            "code_flags": chk.flags,
            "combined": combined,
        })
        if progress:
            progress(f"graded {i + 1}/{len(cases)} {case['id']}")

    stats = {}
    for c in criteria:
        gold = [r["gold"][c] for r in rows]
        stats[c] = {
            "judge": criterion_stats(gold, [r["judge"][c] for r in rows]),
            "combined": criterion_stats(gold, [r["combined"][c] for r in rows]),
            "code_catches": sum(1 for r in rows if r["gold"][c] == "F" and c in r["code_fails"]),
            "code_false_fails": sum(1 for r in rows if r["gold"][c] == "P" and c in r["code_fails"]),
        }

    probe_results = None
    injection_flip = {c: None for c in criteria}
    if run_probes and not isinstance(grader, ReplayGrader):
        probe_results = _run_probes(cases, rows, rubric, grader, criteria, progress)
        for c in criteria:
            pairs = sum(probe_results[p]["by_criterion"][c]["pairs"] for p in PROBES if PROBES[p]["kind"] == "injection")
            flips = sum(probe_results[p]["by_criterion"][c]["flips"] for p in PROBES if PROBES[p]["kind"] == "injection")
            injection_flip[c] = flips / pairs if pairs else None

    bar = rubric["automation_bar"]
    decisions = {}
    for crit in rubric["criteria"]:
        c = crit["id"]
        d = decide(crit, stats[c]["combined"], bar, injection_flip[c])
        if d["status"] == "automate":
            d["route"] = "code + judge" if crit.get("code_check") else "judge"
        else:
            d["route"] = "human review"
        decisions[c] = d

    return {
        "meta": {
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset": {"name": dataset.get("name"), "version": dataset.get("version"), "fingerprint": fingerprint(cases)},
            "rubric": {"name": rubric.get("name"), "version": rubric.get("version"), "fingerprint": fingerprint(rubric["criteria"])},
            "grader": grader.version,
            "n_cases": len(cases),
            "probes_run": probe_results is not None,
        },
        "criteria": [{k: v for k, v in c.items()} for c in rubric["criteria"]],
        "automation_bar": bar,
        "rows": rows,
        "stats": stats,
        "probes": probe_results,
        "decisions": decisions,
    }


def _run_probes(cases, rows, rubric, grader, criteria, progress):
    base = {r["id"]: r["judge"] for r in rows}
    targets = [c for c in cases if "F" in c["gold_labels"].values()]
    results = {}
    for name, spec in PROBES.items():
        by_c = {c: {"pairs": 0, "flips": 0, "cases": []} for c in criteria}
        for case in targets:
            probed = apply_probe(case, name)
            chk = run_checks(probed)
            verdicts = grader.grade(probed, rubric, chk.flags, chk.hard_fails)
            for c in criteria:
                if case["gold_labels"][c] == "F" and base[case["id"]][c] == "F":
                    by_c[c]["pairs"] += 1
                    if verdicts[c]["verdict"] == "P":
                        by_c[c]["flips"] += 1
                        by_c[c]["cases"].append(case["id"])
            if progress:
                progress(f"probe {name}: {case['id']}")
        pairs = sum(v["pairs"] for v in by_c.values())
        flips = sum(v["flips"] for v in by_c.values())
        results[name] = {
            "label": spec["label"], "adds": spec["adds"], "kind": spec["kind"],
            "pairs": pairs, "flips": flips, "flip_rate": flips / pairs if pairs else None,
            "by_criterion": by_c,
        }
    return results
