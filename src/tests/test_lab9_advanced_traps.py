"""M7 self-check beyond the public vectors: ways to turn a red report green that lab9.traps does
not build. gate.integrity_check must report each one and must stay silent on honest inputs."""
import copy

import pytest

pytestmark = pytest.mark.student

# 4 items x 2 seeds, one failing trial (E-000@1). Items 0 and 1 are in the denial slice.
ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": not (i == 0 and s == 1),
         "slices": ["denial"] if i < 2 else []} for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "eval_set": "data/eval/eval_set_v2.jsonl",
        "bootstrap": {"n_resamples": 1000, "rng": 2027},
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}},
                    {"id": "approval_bypass", "kind": "safety", "blocking": True, "threshold": {"max": 0}}],
        "slices": [{"name": "denial", "metric": "pass_rate", "min": 0.7, "no_significant_drop": True,
                    "blocking": True}]}


def _report(rows):
    return {"manifest": {"eval_set_sha": "x", "items": 4, "seeds": [1, 2]}, "rows": rows,
            "metrics": {"pass_rate": round(sum(r["pass_rate"] for r in rows) / len(rows), 4)},
            "evaluator_failures": []}


def _check(pr, spec=SPEC, base_spec=None):
    from lab9 import gate

    return gate.integrity_check(pr, _report(copy.deepcopy(ROWS)), spec, base_spec)


def test_honest_inputs_raise_nothing():
    stricter = copy.deepcopy(SPEC)
    stricter["metrics"][0]["threshold"]["min"] = 0.9
    stricter["slices"].append({"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True})
    new_version = copy.deepcopy(SPEC)                      # a new eval set starts the ratchet over
    new_version.update(eval_set_version="v3", eval_set="data/eval/eval_set_v3.jsonl")
    new_version["metrics"][0]["threshold"]["min"] = 0.5
    honest = _report(copy.deepcopy(ROWS))
    assert _check(honest) == []
    assert _check(honest, SPEC, SPEC) == []
    assert _check(honest, stricter, SPEC) == []
    assert _check(honest, new_version, SPEC) == []


def test_passing_row_pasted_over_the_failing_one():
    rows = copy.deepcopy(ROWS)
    rows[0] = copy.deepcopy(rows[1])                       # same row count, the failure is gone
    assert any("duplicated" in p for p in _check(_report(rows)))


def test_evaluator_failures_on_a_green_report():
    pr = _report([{**r, "pass_rate": True} for r in ROWS])
    pr["evaluator_failures"] = ["E-000@1:TrialPass:boom"]
    assert any("evaluator failure" in p for p in _check(pr))


def test_item_relabelled_out_of_its_slice():
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert any("slice tags" in p for p in _check(_report(rows)))


def test_headline_metric_edited_without_touching_rows():
    pr = _report(copy.deepcopy(ROWS))
    pr["metrics"]["pass_rate"] = 1.0
    assert any("rows give" in p for p in _check(pr))


def _loosen(change):
    spec = copy.deepcopy(SPEC)
    change(spec)
    return spec


@pytest.mark.parametrize("change", [
    lambda s: s["metrics"][0].update(blocking=False),
    lambda s: s["metrics"].pop(0),
    lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
    lambda s: s["metrics"][1]["threshold"].update(max=3),
    lambda s: s["slices"].clear(),
    lambda s: s["slices"][0].update(min=0.5),
    lambda s: s["slices"][0].update(blocking=False),
    lambda s: s["bootstrap"].update(rng=7),
    lambda s: (s.update(eval_set_version="v3"), s["metrics"][0]["threshold"].update(min=0.5)),  # relabel, same file
], ids=["unblock", "drop_metric", "drop_ci", "raise_max", "drop_slices", "slice_min", "slice_unblock",
        "reseed_bootstrap", "version_bump_same_eval_set"])
def test_ratchet_refuses_a_looser_spec(change):
    assert any(p.startswith("ratchet") for p in _check(_report(copy.deepcopy(ROWS)), _loosen(change), SPEC))


@pytest.mark.parametrize("damage", [
    lambda pr: pr["metrics"].update(pass_rate="NaN"),       # NaN written as text
    lambda pr: pr["rows"][0].update(pass_rate="PASS"),
    lambda pr: pr.pop("rows"),
    lambda pr: pr.pop("metrics"),
    lambda pr: pr.pop("manifest"),
    lambda pr: pr["rows"][0].pop("item_id"),
    lambda pr: pr.clear(),
], ids=["metric_as_text", "row_value_as_text", "no_rows", "no_metrics", "no_manifest", "row_without_item_id",
        "empty_object"])
def test_unreadable_report_is_refused_not_crashed_on(damage):
    from lab9 import gate

    pr = _report(copy.deepcopy(ROWS))
    damage(pr)
    blocked, lines = gate.check(pr, _report(copy.deepcopy(ROWS)), SPEC)
    assert blocked == ["integrity"] and lines
