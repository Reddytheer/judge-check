"""One-page HTML report for a run record."""
from __future__ import annotations

from html import escape

CSS = """
:root{--bg:#F6F7F8;--surface:#fff;--sunken:#EEF1F2;--line:#D9DEE0;--fg:#1B2427;--muted:#5C686D;
--accent:#1F5F5B;--pass:#1E7A46;--pass-soft:#DDF1E4;--fail:#B3261E;--fail-soft:#F8E0DE;--warn:#8A5A00;--warn-soft:#F7EBCF}
@media (prefers-color-scheme:dark){:root{--bg:#121719;--surface:#1A2123;--sunken:#20292C;--line:#2F3A3D;--fg:#E3E9EA;
--muted:#98A6AA;--accent:#6FC2B9;--pass:#6CCB93;--pass-soft:#183224;--fail:#F08A80;--fail-soft:#3A1E1C;--warn:#E2B45A;--warn-soft:#362B14;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 "Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px max(16px,env(safe-area-inset-left))}
h1{font:600 26px Georgia,serif;margin:0}h2{font:600 18px Georgia,serif;margin:28px 0 10px}
.meta{color:var(--muted);font-size:13px;margin-top:4px}.lead{font-size:16px;margin:16px 0 0;max-width:70ch}
.tw{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:760px;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);background:var(--sunken)}
tr:last-child td{border-bottom:0}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace}.muted{color:var(--muted)}
.pill{display:inline-block;font-weight:600;font-size:12px;padding:2px 9px;border-radius:999px;white-space:nowrap}
.auto{background:var(--pass-soft);color:var(--pass)}.human{background:var(--warn-soft);color:var(--warn)}
.F{color:var(--fail);font-weight:600}.P{color:var(--pass);font-weight:600}
ul.r{margin:0;padding-left:16px}.note{color:var(--muted);font-size:12.5px;margin-top:8px;max-width:80ch}
"""


def _pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def _k(x):
    return "n/a" if x is None else f"{x:.2f}"


def render(run: dict, title: str = "judge-check report") -> str:
    m = run["meta"]
    crit = {c["id"]: c for c in run["criteria"]}
    dec = run["decisions"]
    n_auto = sum(d["status"] == "automate" for d in dec.values())
    g = m["grader"]
    head = (
        f"<h1>{escape(title)}</h1>"
        f"<div class='meta'>Grader <span class='mono'>{escape(g['grader'])}</span>"
        + (f" · prompt <span class='mono'>{escape(g['system_prompt'])}</span>" if "system_prompt" in g else "")
        + f" · rubric {escape(str(m['rubric']['version']))} <span class='mono'>{m['rubric']['fingerprint']}</span>"
        f" · dataset {escape(str(m['dataset']['version']))} <span class='mono'>{m['dataset']['fingerprint']}</span>"
        f" · {m['n_cases']} cases · {escape(m['run_at'])}</div>"
        f"<p class='lead'><b>{n_auto} of {len(dec)} criteria</b> meet the bar to be graded automatically. "
        f"The other {len(dec) - n_auto} stay with human review.</p>"
    )

    rows = []
    for cid, d in dec.items():
        s = run["stats"][cid]["combined"]
        code = run["stats"][cid]
        cls = "auto" if d["status"] == "automate" else "human"
        rows.append(
            f"<tr><td class='mono'>{cid}</td><td><b>{escape(crit[cid]['name'])}</b><div class='muted'>{escape(crit[cid]['severity'])} · {escape(crit[cid]['lens'])}</div></td>"
            f"<td><span class='pill {cls}'>{'Automate' if cls == 'auto' else 'Human review'}</span>{f"<div class='muted'>via {escape(d['route'])}</div>" if cls == 'auto' else ''}</td>"
            f"<td class='num'>{_pct(s['agreement'])}</td><td class='num'>{_k(s['kappa'])}</td>"
            f"<td class='num'>{s['false_pass']} of {s['gold_fails']}</td><td class='num'>{s['false_fail']}</td>"
            f"<td class='num'>{code['code_catches']}</td>"
            f"<td><ul class='r'>{''.join(f'<li>{escape(r)}</li>' for r in d['reasons'])}</ul></td></tr>"
        )
    decisions = (
        "<h2>Decision per criterion</h2><div class='tw'><table><thead><tr><th>ID</th><th>Criterion</th><th>Decision</th>"
        "<th class='num'>Agreement</th><th class='num'>Kappa</th><th class='num'>Missed failures</th><th class='num'>False fails</th>"
        "<th class='num'>Caught by code</th><th>Why</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        "<p class='note'>Metrics use code checks plus the grader, measured against the reviewed gold labels. "
        "A missed failure is a false pass: the grader passed an output the reviewer failed. It is the expensive error in AML, "
        "so Critical criteria need a false-pass rate at or below "
        f"{run['automation_bar']['max_false_pass_rate_critical']:.0%} of all graded cases.</p>"
    )

    if run.get("probes"):
        prow = "".join(
            f"<tr><td><b>{escape(p['label'])}</b><div class='muted'>{escape(p['adds'])}</div></td><td>{escape(p['kind'])}</td>"
            f"<td class='num'>{p['pairs']}</td><td class='num'>{p['flips']}</td><td class='num'>{_pct(p['flip_rate'])}</td>"
            f"<td class='mono'>{escape(', '.join(sorted({x for v in p['by_criterion'].values() for x in v['cases']})) or '-')}</td></tr>"
            for p in run["probes"].values()
        )
        probes = (
            "<h2>Attacks on the judge</h2><div class='tw'><table><thead><tr><th>Probe</th><th>Kind</th><th class='num'>Fail verdicts tested</th>"
            "<th class='num'>Flipped to Pass</th><th class='num'>Flip rate</th><th>Cases flipped</th></tr></thead><tbody>"
            + prow + "</tbody></table></div><p class='note'>Each probe rewrites a failing output without fixing it. A flip means the judge was steered.</p>"
        )
    else:
        probes = "<h2>Attacks on the judge</h2><p class='note'>Not run for this grader. Probes need a grader that reads the text (run with <span class='mono'>--grader llm --probes</span>).</p>"

    dis = []
    for r in run["rows"]:
        for cid in crit:
            if r["combined"][cid] != r["gold"][cid]:
                dis.append(
                    f"<tr><td class='mono'>{r['id']}</td><td class='mono'>{cid}</td><td class='{r['gold'][cid]}'>{r['gold'][cid]}</td>"
                    f"<td class='{r['combined'][cid]}'>{r['combined'][cid]}</td><td>{escape(r['judge_reasons'][cid])}</td>"
                    f"<td>{escape(r.get('review_note', ''))}</td></tr>"
                )
    disagree = (
        f"<h2>Disagreements ({len(dis)})</h2>"
        + ("<div class='tw'><table><thead><tr><th>Case</th><th>Crit.</th><th>Gold</th><th>Grader</th><th>Grader reason</th><th>Review note</th></tr></thead><tbody>"
           + "".join(dis) + "</tbody></table></div>" if dis else "<p class='note'>None.</p>")
    )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{CSS}</style></head><body><div class='wrap'>"
        + head + decisions + probes + disagree + "</div></body></html>"
    )
