"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = _report_problems(pr, "PR") + _report_problems(base, "baseline")
    pr_keys, base_keys = _row_keys(pr), _row_keys(base)
    if set(pr_keys) != set(base_keys):
        gone, extra = sorted(set(base_keys) - set(pr_keys)), sorted(set(pr_keys) - set(base_keys))
        problems.append(f"PR (item, seed) set differs from the baseline's: {len(gone)} missing"
                        f" (e.g. {gone[:2]}), {len(extra)} extra (e.g. {extra[:2]})")
    # A crashed grader scores None and silently leaves the mean: every metric the baseline graded
    # per row must have a real value on every PR row.
    ids = {m["id"] for m in spec["metrics"]}
    graded = sorted(ids & {k for r in base["rows"] + pr["rows"] for k in r})
    holes = Counter(m for r in pr["rows"] for m in graded if r.get(m) is None)
    problems += [f"{n} PR row(s) have no value for {m} (grader crashed or result removed)"
                 for m, n in sorted(holes.items())]
    problems += _metric_drift(pr, graded, spec)
    tags = {r["item_id"]: sorted(r.get("slices") or []) for r in base["rows"]}
    moved = sorted({r["item_id"] for r in pr["rows"]
                    if r["item_id"] in tags and sorted(r.get("slices") or []) != tags[r["item_id"]]})
    if moved:
        problems.append(f"slice tags differ from the baseline's for {len(moved)} item(s), e.g. {moved[:3]}")
    if base_spec is not None:
        problems += _ratchet(spec, base_spec)
    return problems


def _row_keys(rep: dict) -> Counter:
    return Counter((r.get("item_id"), r.get("seed")) for r in rep["rows"])


def _report_problems(rep: dict, who: str) -> list[str]:
    """Checks one report can fail on its own: non-finite metrics, broken graders, row bookkeeping."""
    problems = [f"{who} metric {k} is {v}" for k, v in rep.get("metrics", {}).items()
                if isinstance(v, float) and not math.isfinite(v)]
    if rep.get("evaluator_failures"):
        problems.append(f"{who} has {len(rep['evaluator_failures'])} evaluator failure(s): graders did not run cleanly")
    manifest = rep.get("manifest", {})
    if "items" in manifest and "seeds" in manifest:
        want = int(manifest["items"]) * len(manifest["seeds"])
        if len(rep["rows"]) != want:
            problems.append(f"{who} has {len(rep['rows'])} rows, manifest says {manifest['items']} items x "
                            f"{len(manifest['seeds'])} seeds = {want}")
    dupes = sorted(k for k, n in _row_keys(rep).items() if n > 1)
    if dupes:
        problems.append(f"{who} has duplicated (item, seed) rows, e.g. {dupes[:3]}")
    return problems


def _metric_drift(pr: dict, graded: list[str], spec: dict) -> list[str]:
    """The headline numbers must be what the rows add up to: a hand-edited summary is not evidence."""
    rows = [{**r, **{m: r.get(m) for m in graded}, "cost": r.get("cost", 0.0)} for r in pr["rows"]]
    fresh = aggregate(rows, graded, k_values=spec.get("pass_k", []))
    if not all("cost" in r for r in pr["rows"]):
        fresh.pop("cost_per_success", None)
    out = []
    for k, v in fresh.items():
        got = pr.get("metrics", {}).get(k)
        if isinstance(v, (int, float)) and isinstance(got, (int, float)) and not abs(got - v) <= 1e-4:
            out.append(f"PR metric {k} is reported as {got} but its rows give {v}")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Same eval set => a threshold may only get stricter. A new eval-set version starts over."""
    same_set = spec.get("eval_set_version") == base_spec.get("eval_set_version") or (
        spec.get("eval_set") is not None and spec.get("eval_set") == base_spec.get("eval_set"))
    if not same_set:
        return []
    out = []
    if spec.get("bootstrap") != base_spec.get("bootstrap"):
        out.append("ratchet: bootstrap settings changed on the same eval set (re-baseline under a new version)")

    def looser(what: str, old: dict, new: dict | None, old_th: dict, new_th: dict) -> None:
        if new is None:
            out.append(f"ratchet: {what} was removed")
            return
        for key, worse in (("min", lambda a, b: b < a), ("max", lambda a, b: b > a),
                           ("max_increase", lambda a, b: b > a)):
            if key in old_th and (key not in new_th or worse(old_th[key], new_th[key])):
                out.append(f"ratchet: {what} {key} loosened {old_th[key]} -> {new_th.get(key, 'removed')}")
        if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
            out.append(f"ratchet: {what} dropped no_significant_drop")
        if old.get("blocking") and not new.get("blocking"):
            out.append(f"ratchet: {what} is no longer blocking")

    new_metrics = {m["id"]: m for m in spec.get("metrics") or []}
    for m in base_spec.get("metrics") or []:
        new = new_metrics.get(m["id"])
        looser(f"metric {m['id']}", m, new, m.get("threshold") or {}, (new or {}).get("threshold") or {})
    new_slices = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for sl in base_spec.get("slices") or []:
        looser(f"slice {sl['name']}/{sl['metric']}", sl, new_slices.get((sl["name"], sl["metric"])),
               sl, new_slices.get((sl["name"], sl["metric"])) or {})
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        th = {k: sl[k] for k in ("min", "max", "no_significant_drop") if k in sl}
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note = "ok", ""
        val = round(sum(a.values()) / len(a), 4) if a else None
        if val is None:
            verdict = "missing"            # no graded row in the slice: nothing shows it is healthy
        elif ("min" in sl and val < sl["min"]) or ("max" in sl and val > sl["max"]):
            verdict = "fail"
        if sl.get("no_significant_drop") and val is not None:
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        lines.append(f"  {sid:<34} {val!s:<8} n={len(a):<3} {json.dumps(th):<34} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
