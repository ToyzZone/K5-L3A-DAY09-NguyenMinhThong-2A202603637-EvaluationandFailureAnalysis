"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError(f"human has {len(human)} labels, judge has {len(judge)}")
    cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        h_pos, j_pos = str(h).strip().upper() == POS, str(j).strip().upper() == POS
        cm[("t" if h_pos == j_pos else "f") + ("p" if j_pos else "n")] += 1
    return cm


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    flagged, real = cm["tp"] + cm["fp"], cm["tp"] + cm["fn"]
    return (cm["tp"] / flagged if flagged else 0.0, cm["tp"] / real if real else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa is undefined on zero labels")
    p_o = (cm["tp"] + cm["tn"]) / n
    human_pos, judge_pos = (cm["tp"] + cm["fn"]) / n, (cm["tp"] + cm["fp"]) / n
    p_e = human_pos * judge_pos + (1 - human_pos) * (1 - judge_pos)
    if math.isclose(p_e, 1.0):
        raise ValueError("kappa is undefined: both raters are constant (p_e == 1)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].
    NaN when sensitivity + specificity <= 1: a judge no better than chance carries no
    information to correct with, and any number returned here would be invented."""
    informativeness = sensitivity + specificity - 1
    if informativeness <= 0:
        return float("nan")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / informativeness))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError(f"paired samples need the same items in the same order, got {x.shape} vs {y.shape}")
    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0
    diff = float(x.mean() - y.mean())
    if x.size < 2:
        # One pair: every resample is that pair, so the percentile interval collapses onto the
        # difference. scipy refuses n < 2, so return the degenerate interval directly.
        return diff, diff, diff

    def mean_diff(u, v, axis=-1):
        return np.mean(u, axis=axis) - np.mean(v, axis=axis)

    ci = bootstrap((x, y), mean_diff, paired=True, vectorized=True, n_resamples=n_resamples,
                   confidence_level=confidence, method="percentile",
                   rng=np.random.default_rng(rng)).confidence_interval
    return diff, float(ci.low), float(ci.high)


def _check_nck(n: int, c: int, k: int) -> None:
    """n trials, c of them passing, draw k: all integers with 0 <= c <= n and 1 <= k <= n."""
    if not all(isinstance(v, Integral) for v in (n, c, k)):
        raise ValueError(f"n, c, k must be integers, got {(n, c, k)!r}")
    if n < 1 or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError(f"need n >= 1, 0 <= c <= n and 1 <= k <= n, got n={n}, c={c}, k={k}")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _check_nck(n, c, k)
    return 1 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _check_nck(n, c, k)
    return math.comb(c, k) / math.comb(n, k)
