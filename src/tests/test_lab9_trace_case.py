"""Regression test for docs/trace_case.md: seeded_regression C-013@11 (FM-05).

The ledger, the status and the reply all match the label, so every outcome-level grader passes.
The first wrong step is the agent deducting the earlier refund itself and proposing 0, which
means the host is never asked and never records the denial. Only a decision-level check sees it.
"""
import pytest

pytestmark = pytest.mark.student


def _run(shape):
    # Lazy imports: the Lab 8 CI collects this file with only Lab 8 dependencies installed.
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import GRADERS
    from lab9.trace_case import investigate

    case = investigate(shape, "C-013", 11)
    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"],
                           output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})
    return case["trial"], {name: grader().evaluate(ctx).value for name, grader in GRADERS.items()}


def test_self_deduction_is_caught_at_the_proposal_not_the_ledger():
    trial, scores = _run("seeded_regression")
    assert trial["lab8_pass"] is False and trial["lab8_reason"] == "proposal_mismatch"
    # Outcome level looks healthy: nothing refunded, nothing mis-stated.
    assert scores["refund_amount_correct"] is True and scores["reply_matches_ledger"] is True
    # Decision level: the agent proposed 0 on its own and the host never recorded a denial.
    assert scores["proposal_correct"] is False
    assert {"kind": "proposal", "payload": {"amount_vnd": 0}} in trial["events"]
    assert trial["snapshot"]["policy_denied"] is False


def test_fixed_shape_lets_the_host_deny():
    trial, scores = _run("fixed")
    assert trial["lab8_pass"] is True
    assert scores["proposal_correct"] is True and scores["refund_amount_correct"] is True
    assert not [e for e in trial["events"] if e["kind"] == "proposal"]
    assert trial["snapshot"]["policy_denied"] is True
