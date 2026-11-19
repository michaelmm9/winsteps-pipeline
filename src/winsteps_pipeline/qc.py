"""Automated quality-control flags for parsed WINSTEPS item and person tables.

Every check produces one row in a "flags" table, so the result can be read by a person,
filtered, counted, saved, or compared with an earlier run. Flags are prompts for review,
not decisions: removing an item or person is a human (psychometrician) call.
"""
from dataclasses import dataclass

import pandas as pd

FLAG_COLUMNS = ["kind", "label", "check", "severity", "value", "threshold", "message"]
SEVERITY_ORDER = {"review": 0, "note": 1}


@dataclass(frozen=True)
class QCThresholds:
    """Rule-of-thumb cutoffs. Programs set their own, so treat these as defaults to adjust."""
    infit_max: float = 1.3
    infit_min: float = 0.7
    outfit_max: float = 1.3
    outfit_min: float = 0.7
    ptmeasure_low: float = 0.10      # observed point-measure correlation below this
    se_max: float = 0.50             # item standard error above this
    person_infit_max: float = 1.5    # persons answer fewer items, so their statistics are noisier
    person_outfit_max: float = 1.5
    drift_max: float = 0.30          # change in item measure between runs, after removing the shift


def _flag(kind, label, check, severity, value, threshold, message):
    return {"kind": kind, "label": label, "check": check, "severity": severity,
            "value": value, "threshold": threshold, "message": message}


def _as_frame(rows):
    return pd.DataFrame(rows, columns=FLAG_COLUMNS)


def flag_items(items, th=None):
    """Flag items on fit, point-measure correlation, precision, and status."""
    th = th or QCThresholds()
    rows = []
    for r in items.itertuples():
        infit_high = r.infit > th.infit_max
        if infit_high:
            rows.append(_flag("item", r.label, "infit_high", "review", r.infit, th.infit_max,
                              "Noisier than the model expects among on-target responses"))
        if r.infit < th.infit_min:
            rows.append(_flag("item", r.label, "infit_low", "note", r.infit, th.infit_min,
                              "More predictable than expected: possible dependence or very high discrimination"))
        if r.outfit > th.outfit_max:
            # High outfit with normal infit means a few outlying responses, which is less serious
            sev = "review" if infit_high else "note"
            rows.append(_flag("item", r.label, "outfit_high", sev, r.outfit, th.outfit_max,
                              "A few unexpected responses far from the item's difficulty"
                              if not infit_high else "Unexpected responses; infit is also high"))
        if r.outfit < th.outfit_min:
            rows.append(_flag("item", r.label, "outfit_low", "note", r.outfit, th.outfit_min,
                              "Overly predictable responses"))
        if r.ptmeasure_corr < 0:
            rows.append(_flag("item", r.label, "ptmeasure_negative", "review", r.ptmeasure_corr, 0.0,
                              "Negative point-measure correlation: check the key and scoring"))
        elif r.ptmeasure_corr < th.ptmeasure_low:
            rows.append(_flag("item", r.label, "ptmeasure_low", "review", r.ptmeasure_corr,
                              th.ptmeasure_low, "Item barely relates to ability: weak discrimination or off-construct"))
        if r.se > th.se_max:
            rows.append(_flag("item", r.label, "se_high", "note", r.se, th.se_max,
                              "Imprecise estimate, usually a very easy or very hard item"))
        if r.status != 1:
            rows.append(_flag("item", r.label, "status", "note", r.status, 1,
                              "Status code other than 1: check the WINSTEPS manual for its meaning"))
    return _as_frame(rows)


def flag_persons(persons, th=None):
    """Flag persons on fit, extreme scores, and status."""
    th = th or QCThresholds()
    rows = []
    for r in persons.itertuples():
        infit_high = r.infit > th.person_infit_max
        if infit_high:
            rows.append(_flag("person", r.label, "infit_high", "review", r.infit, th.person_infit_max,
                              "Response pattern is noisier than expected"))
        if r.outfit > th.person_outfit_max:
            sev = "review" if infit_high else "note"
            rows.append(_flag("person", r.label, "outfit_high", sev, r.outfit, th.person_outfit_max,
                              "Unexpected responses; infit is also high" if infit_high
                              else "A few unexpected responses, possibly a single slip"))
        if r.score <= 0 or r.score >= r.count:
            rows.append(_flag("person", r.label, "extreme_score", "note", r.score, r.count,
                              "All wrong or all right: the measure is an estimate, not a finite maximum likelihood value"))
        if r.status != 1:
            rows.append(_flag("person", r.label, "status", "note", r.status, 1,
                              "Status code other than 1: check the WINSTEPS manual for its meaning"))
    return _as_frame(rows)


def compare_item_measures(current, previous, th=None):
    """Compare item measures with an earlier run (the anchor-drift idea from Module 4).

    Each run is centered on its own items, so the typical change (the median difference)
    is removed first. An item is flagged when it moves by more than drift_max beyond that.
    Returns (flags, table), where table shows each shared item's difference and deviation.
    """
    th = th or QCThresholds()
    merged = current[["label", "measure"]].merge(
        previous[["label", "measure"]], on="label", how="outer",
        suffixes=("_now", "_before"), indicator=True)

    both = merged[merged["_merge"] == "both"].copy()
    both["diff"] = both["measure_now"] - both["measure_before"]
    shift = both["diff"].median() if len(both) else 0.0
    both["deviation"] = both["diff"] - shift

    rows = []
    for r in both.itertuples():
        if abs(r.deviation) > th.drift_max:
            rows.append(_flag("item", r.label, "drift", "review", round(r.deviation, 3), th.drift_max,
                              f"Moved {r.deviation:+.2f} logits relative to the typical shift of {shift:+.2f}"))
    for r in merged[merged["_merge"] == "left_only"].itertuples():
        rows.append(_flag("item", r.label, "new_item", "note", None, None, "Not present in the earlier run"))
    for r in merged[merged["_merge"] == "right_only"].itertuples():
        rows.append(_flag("item", r.label, "missing_item", "review", None, None,
                          "Present in the earlier run but not in this one"))
    table = both[["label", "measure_before", "measure_now", "diff", "deviation"]].reset_index(drop=True)
    return _as_frame(rows), table


def run_qc(items, persons, previous_items=None, th=None):
    """Run every check and return one flags table, with the most serious flags first."""
    th = th or QCThresholds()
    parts = [flag_items(items, th), flag_persons(persons, th)]
    if previous_items is not None:
        parts.append(compare_item_measures(items, previous_items, th)[0])
    flags = pd.concat(parts, ignore_index=True)
    flags["_rank"] = flags["severity"].map(SEVERITY_ORDER)
    flags = (flags.sort_values(["_rank", "kind", "label", "check"], kind="stable")
                  .drop(columns="_rank").reset_index(drop=True))
    return flags


def summarize(flags):
    """Count flags by kind and severity."""
    if flags.empty:
        return pd.DataFrame()
    return flags.groupby(["kind", "severity"]).size().unstack(fill_value=0)