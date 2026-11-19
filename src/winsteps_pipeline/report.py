"""Build a one-page HTML summary of a calibration for a psychometrician to read."""
import dataclasses
import html
import platform
from datetime import datetime
from importlib import metadata
from pathlib import Path

import pandas as pd

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;font-size:13px;color:#1a1a1a;margin:24px;max-width:1000px}
h1{font-size:20px;margin:0 0 2px} h2{font-size:15px;margin:22px 0 6px;border-bottom:1px solid #ccc;padding-bottom:3px}
.sub{color:#555;margin:0 0 14px}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.card{border:1px solid #ccc;border-radius:6px;padding:8px 12px;min-width:120px}
.card b{display:block;font-size:20px}
.card.alert{border-color:#b3261e;background:#fdecea}
table{border-collapse:collapse;width:100%;margin:4px 0}
th,td{border-bottom:1px solid #ddd;padding:3px 8px;text-align:right}
th{background:#f2f2f2} td.l,th.l{text-align:left}
tr.review td{background:#fdecea} tr.note td{background:#fff8e1}
.small{color:#555;font-size:12px} .box{background:#f7f7f7;border-radius:6px;padding:8px 12px}
@media print{body{margin:10mm;font-size:11px}}
"""

ITEM_COLUMNS = [("label", "Item", "l", None), ("measure", "Measure", "", "{:.2f}"),
                ("se", "S.E.", "", "{:.2f}"), ("infit", "Infit", "", "{:.2f}"),
                ("outfit", "Outfit", "", "{:.2f}"), ("ptmeasure_corr", "Pt-meas. corr.", "", "{:.2f}")]
PERSON_COLUMNS = [("label", "Person", "l", None), ("measure", "Measure", "", "{:.2f}"),
                  ("score", "Score", "", "{:.0f}"), ("infit", "Infit", "", "{:.2f}"),
                  ("outfit", "Outfit", "", "{:.2f}")]


def _esc(value):
    return html.escape(str(value))


def _table(rows, columns, flag_col=True):
    """Build an HTML table. rows is a list of (record_dict, severity_or_None, flag_text)."""
    head = "".join(f'<th class="{c}">{_esc(t)}</th>' for _, t, c, _ in columns)
    if flag_col:
        head += '<th class="l">Flags</th>'
    body = []
    for record, severity, flag_text in rows:
        cells = []
        for key, _, cls, fmt in columns:
            value = record[key]
            text = _esc(value) if fmt is None else fmt.format(value)
            cells.append(f'<td class="{cls}">{text}</td>')
        if flag_col:
            cells.append(f'<td class="l">{_esc(flag_text)}</td>')
        body.append(f'<tr class="{severity or ""}">{"".join(cells)}</tr>')
    return f"<table><tr>{head}</tr>{''.join(body)}</table>"


def _flag_summary(flags, kind):
    """Map label -> (worst severity, comma-joined check names) for one kind of flag."""
    out = {}
    sub = flags[flags["kind"] == kind]
    for label, grp in sub.groupby("label"):
        severity = "review" if (grp["severity"] == "review").any() else "note"
        out[label] = (severity, ", ".join(grp["check"]))
    return out


def build_report_html(cfg, items, persons, flags, thresholds, sources=None,
                      comparison=None, generated_at=None, max_person_rows=40):
    """Return the report as an HTML string.

    sources     dict of description -> file path (only file names are shown)
    comparison  optional (flags, table) pair from compare_item_measures
    """
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    item_flags = _flag_summary(flags, "item")
    person_flags = _flag_summary(flags, "person")
    n_item_review = sum(1 for s, _ in item_flags.values() if s == "review")
    n_person_review = sum(1 for s, _ in person_flags.values() if s == "review")
    n_notes = int((flags["severity"] == "note").sum())

    try:
        version = metadata.version("winsteps-pipeline")
    except metadata.PackageNotFoundError:
        version = "unknown"

    parts = [f"<h1>Calibration QC summary</h1>",
             f'<p class="sub">{_esc(cfg.title)} &middot; generated {_esc(generated_at)}</p>']

    alert = " alert" if (n_item_review or n_person_review) else ""
    parts.append('<div class="cards">'
                 f'<div class="card"><b>{len(items)}</b>items</div>'
                 f'<div class="card"><b>{len(persons)}</b>persons</div>'
                 f'<div class="card{alert}"><b>{n_item_review}</b>items to review</div>'
                 f'<div class="card{alert}"><b>{n_person_review}</b>persons to review</div>'
                 f'<div class="card"><b>{n_notes}</b>other notes</div></div>')

    # Items: the full table by difficulty, with flagged rows colored
    parts.append("<h2>Items</h2>")
    ordered = items.sort_values("measure", ascending=False)
    rows = []
    for rec in ordered.to_dict("records"):
        sev, text = item_flags.get(rec["label"], (None, ""))
        rows.append((rec, sev, text))
    parts.append(_table(rows, ITEM_COLUMNS))
    parts.append('<p class="small">Sorted from hardest to easiest. Red rows need review; '
                 'amber rows are notes.</p>')

    # Persons: only flagged ones, review first, capped
    parts.append("<h2>Persons with flags</h2>")
    flagged = persons[persons["label"].isin(person_flags)].copy()
    flagged["_rank"] = flagged["label"].map(lambda x: 0 if person_flags[x][0] == "review" else 1)
    flagged = flagged.sort_values(["_rank", "label"])
    shown = flagged.head(max_person_rows)
    if flagged.empty:
        parts.append("<p>No persons were flagged.</p>")
    else:
        rows = [(rec, person_flags[rec["label"]][0], person_flags[rec["label"]][1])
                for rec in shown.to_dict("records")]
        parts.append(_table(rows, PERSON_COLUMNS))
        if len(flagged) > len(shown):
            parts.append(f'<p class="small">Showing {len(shown)} of {len(flagged)} flagged persons.</p>')

    if comparison is not None:
        cmp_flags, table = comparison
        shift = table["diff"].median() if len(table) else 0.0
        parts.append("<h2>Comparison with an earlier run</h2>")
        parts.append(f"<p>Typical change in item measure: <b>{shift:+.2f}</b> logits "
                     f"(removed before judging each item). Items flagged for drift: "
                     f"<b>{int((cmp_flags['check'] == 'drift').sum())}</b>.</p>")
        drifted = cmp_flags[cmp_flags["check"].isin(["drift", "missing_item", "new_item"])]
        if not drifted.empty:
            rows = [(rec, "review" if rec["severity"] == "review" else "note", rec["message"])
                    for rec in drifted.to_dict("records")]
            cols = [("label", "Item", "l", None), ("check", "Check", "l", None)]
            parts.append(_table(rows, cols))

    th = dataclasses.asdict(thresholds)
    th_text = "; ".join(f"{k} = {v}" for k, v in th.items())
    src_text = "; ".join(f"{k}: {Path(v).name}" for k, v in (sources or {}).items()) or "not recorded"
    parts.append("<h2>About this report</h2>")
    parts.append('<div class="box small">'
                 "<p>Flags are prompts for review, not decisions. Whether to keep, revise, or "
                 "remove an item or person is a psychometrician's judgment.</p>"
                 f"<p><b>Thresholds:</b> {_esc(th_text)}</p>"
                 f"<p><b>Source files:</b> {_esc(src_text)}</p>"
                 f"<p><b>Software:</b> winsteps-pipeline {_esc(version)}, "
                 f"Python {_esc(platform.python_version())}, pandas {_esc(pd.__version__)}</p></div>")

    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f"<title>Calibration QC summary</title><style>{CSS}</style></head><body>"
            + "".join(parts) + "</body></html>")


def write_report(path, *args, **kwargs):
    """Build the report and save it. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report_html(*args, **kwargs), encoding="utf-8")
    return path