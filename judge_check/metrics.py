"""Agreement metrics and the per-criterion automation decision."""
from __future__ import annotations


def cohen_kappa(gold: list[str], pred: list[str]) -> float | None:
    n = len(gold)
    if n == 0:
        return None
    po = sum(g == p for g, p in zip(gold, pred)) / n
    pe = sum((gold.count(k) / n) * (pred.count(k) / n) for k in ("P", "F"))
    if pe == 1.0:
        return None  # only one class present in both; kappa undefined
    return (po - pe) / (1 - pe)


def criterion_stats(gold: list[str], pred: list[str]) -> dict:
    n = len(gold)
    false_pass = sum(g == "F" and p == "P" for g, p in zip(gold, pred))
    false_fail = sum(g == "P" and p == "F" for g, p in zip(gold, pred))
    return {
        "n": n,
        "gold_fails": gold.count("F"),
        "agreement": sum(g == p for g, p in zip(gold, pred)) / n if n else None,
        "kappa": cohen_kappa(gold, pred),
        "false_pass": false_pass,
        "false_fail": false_fail,
        "false_pass_rate": false_pass / n if n else None,
    }


def decide(criterion: dict, stats: dict, bar: dict, injection_flip_rate: float | None) -> dict:
    """Return {"status": "automate"|"human", "reasons": [...]} for one criterion."""
    reasons = []
    critical = criterion["severity"] == "critical"
    if stats["gold_fails"] < bar["min_gold_fails"]:
        reasons.append(f"only {stats['gold_fails']} real failures in the set (need {bar['min_gold_fails']}) to trust the judge on misses")
    k = stats["kappa"]
    if k is None or k < bar["min_kappa"]:
        reasons.append(f"kappa {'n/a' if k is None else f'{k:.2f}'} below {bar['min_kappa']:.2f}")
    if critical and stats["false_pass_rate"] > bar["max_false_pass_rate_critical"]:
        reasons.append(
            f"false-pass rate {stats['false_pass_rate']:.1%} above {bar['max_false_pass_rate_critical']:.0%} "
            f"({stats['false_pass']} of {stats['gold_fails']} real failures passed)"
        )
    if critical and injection_flip_rate is not None and injection_flip_rate > bar["max_injection_flip_rate_critical"]:
        reasons.append(f"judge flipped on injection probes ({injection_flip_rate:.0%} of failing verdicts)")
    return {"status": "human" if reasons else "automate", "reasons": reasons or ["meets every bar"]}
