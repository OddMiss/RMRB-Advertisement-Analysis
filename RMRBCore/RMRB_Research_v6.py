"""
RMRB_Research_v6
================
The evidence layer: everything that has to be true *before* a backtest curve is
worth looking at, plus the checks that stop a curve from being an artefact.

The notebooks established the headline finding — RMRB coverage has a negative
Rank IC against next-month industry returns — with a single-path IC plot and a
single equity curve. That is enough to form a hypothesis and nowhere near enough
to trade one. This module adds the parts that decide the question:

* **Monotonicity.** A real factor pays in a ladder across quantiles, not just at
  the extremes. ``quantile_portfolios`` checks that.
* **Horizon.** ``horizon_scan`` measures IC at 1..K months forward so the
  holding period is chosen from evidence rather than convenience.
* **Robustness of significance.** Overlapping holding periods autocorrelate
  returns; the IC t-stat uses a Newey-West correction.
* **Out of sample.** ``split_sample`` enforces one design window and one held-out
  window, and the pipeline reports both.
* **Parameter stability.** ``sensitivity_grid`` sweeps the knobs. A finding that
  survives only at one lookback is a fitted artefact.
* **Multiple testing.** ``deflated_sharpe`` and ``permutation_test`` price in how
  many configurations were tried before the winner appeared.

None of these are optional garnish; they are the difference between "the data
says something" and "I searched until something looked good".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from RMRBCore.RMRB_Backtest_v6 import (
    newey_west_tstat, performance_stats, run_backtest, scores_to_weights,
)
from RMRBCore.RMRB_Factor_v6 import compound_returns


# ---------------------------------------------------------------------------
# Information coefficient
# ---------------------------------------------------------------------------


def rank_ic(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    method: str = "spearman",
) -> pd.Series:
    """Cross-sectional rank correlation between score(t) and return(t+1), per period."""
    common = scores.columns.intersection(forward_returns.columns)
    periods = scores.index.intersection(forward_returns.index)

    values = {}
    for period in periods:
        block = pd.DataFrame({
            "score": scores.loc[period, common],
            "fwd": forward_returns.loc[period, common],
        }).dropna()
        if len(block) < 5:
            continue
        values[period] = block["score"].corr(block["fwd"], method=method)

    return pd.Series(values, name="rank_ic").sort_index()


def ic_summary(ic_series: pd.Series) -> dict:
    """IC mean, IR, Newey-West t-stat and hit rate."""
    clean = ic_series.dropna()
    if clean.empty:
        return {}
    mean = float(clean.mean())
    std = float(clean.std())
    return {
        "ic_mean": mean,
        "ic_std": std,
        "ic_ir": mean / std if std else np.nan,
        "ic_t_stat_nw": float(newey_west_tstat(clean)),
        "ic_positive_rate": float((clean > 0).mean()),
        "n_periods": int(len(clean)),
    }


def horizon_scan(
    scores: pd.DataFrame,
    period_returns: pd.DataFrame,
    horizons=range(1, 13),
) -> pd.DataFrame:
    """IC of score(t) against the cumulative return over t+1 .. t+h.

    Answers "how long does the information stay useful?", which is exactly the
    question a holding period is the answer to.
    """
    log_returns = np.log1p(period_returns)
    rows = {}
    for h in horizons:
        # rolling(h).sum() at j is the sum over j-h+1..j, so shifting it back by
        # h puts the sum over t+1..t+h on row t.
        forward = np.expm1(log_returns.rolling(window=h, min_periods=h).sum().shift(-h))
        rows[h] = ic_summary(rank_ic(scores, forward))
    return pd.DataFrame(rows).T.rename_axis("horizon_months")


# ---------------------------------------------------------------------------
# Quantile ladder
# ---------------------------------------------------------------------------


def quantile_portfolios(
    scores: pd.DataFrame,
    period_returns: pd.DataFrame,
    n_quantiles: int = 5,
    min_names: int = 10,
) -> dict:
    """Equal-weight portfolio return per score quantile, plus the top-minus-bottom spread.

    Monotonic quantile returns are the strongest single piece of evidence that a
    factor is real: a lucky pair of extreme buckets is common, an ordered ladder
    across five buckets is not.
    """
    forward = period_returns.shift(-1)
    periods = scores.index.intersection(forward.index)

    rows = []
    for period in periods:
        block = pd.DataFrame({
            "score": scores.loc[period],
            "fwd": forward.loc[period],
        }).dropna()
        if len(block) < min_names:
            continue
        # Rank first so ties (very common in a masked panel) cannot collapse a bucket.
        buckets = pd.qcut(block["score"].rank(method="first"), n_quantiles,
                          labels=range(1, n_quantiles + 1))
        row = block.groupby(buckets, observed=False)["fwd"].mean()
        row.name = period
        rows.append(row)

    if not rows:
        return {}

    table = pd.DataFrame(rows)
    table.columns = [f"Q{c}" for c in table.columns]
    table["spread"] = table[f"Q{n_quantiles}"] - table["Q1"]

    mean_returns = table.mean()
    monotonic = mean_returns[[f"Q{i}" for i in range(1, n_quantiles + 1)]]
    ladder = monotonic.values
    # Spearman between bucket rank and mean return: +1 is a perfect ladder.
    ladder_rho = float(stats.spearmanr(np.arange(len(ladder)), ladder).statistic)

    return {
        "periodic_returns": table,
        "mean_returns": mean_returns,
        "spread_t_stat_nw": float(newey_west_tstat(table["spread"])),
        "monotonicity_rho": ladder_rho,
        "n_periods": len(table),
    }


# ---------------------------------------------------------------------------
# Event study and lead-lag
# ---------------------------------------------------------------------------


def event_study(
    zscore: pd.DataFrame,
    period_returns: pd.DataFrame,
    threshold: float = 1.5,
    pre: int = 3,
    post: int = 9,
) -> dict:
    """Cumulative abnormal return around attention shocks.

    Abnormal is measured against the equal-weighted industry index, not a
    cap-weighted benchmark: the strategy trades equal-weighted sector blocks, so
    the cap-weighted index would import a size bet into the "abnormal" number.
    """
    common = zscore.columns.intersection(period_returns.columns)
    abnormal = period_returns[common].sub(period_returns[common].mean(axis=1), axis=0)
    z = zscore[common]

    aligned = z.index.intersection(abnormal.index)
    z, abnormal = z.loc[aligned], abnormal.loc[aligned]
    labels = [f"T{k:+d}" if k else "T" for k in range(-pre, post + 1)]

    neglect, hype = [], []
    for i in range(pre, len(aligned) - post - 1):
        for industry in common:
            value = z.iloc[i][industry]
            if pd.isna(value) or abs(value) < threshold:
                continue
            window = abnormal[industry].iloc[i - pre: i + post + 1].values
            if len(window) != len(labels) or np.isnan(window).any():
                continue
            car = np.cumsum(window)
            car -= car[pre]                      # re-base at the event month
            (neglect if value <= -threshold else hype).append(car)

    result = {"labels": labels, "n_neglect": len(neglect), "n_hype": len(hype)}
    if neglect:
        result["car_neglect"] = pd.Series(np.mean(neglect, axis=0), index=labels)
    if hype:
        result["car_hype"] = pd.Series(np.mean(hype, axis=0), index=labels)
    if neglect and hype:
        result["car_spread"] = result["car_neglect"] - result["car_hype"]
        # Is the post-event spread distinguishable from zero at T+post?
        end_neglect = np.array([c[-1] - c[pre] for c in neglect])
        end_hype = np.array([c[-1] - c[pre] for c in hype])
        t_stat, p_value = stats.ttest_ind(end_neglect, end_hype, equal_var=False)
        result["spread_t_stat"] = float(t_stat)
        result["spread_p_value"] = float(p_value)
    return result


def lead_lag(
    scores: pd.DataFrame,
    period_returns: pd.DataFrame,
    max_lag: int = 6,
) -> pd.Series:
    """Average correlation of score(t) with return(t+k) for k in [-max_lag, +max_lag].

    Negative k tests whether coverage merely *echoes* past price action; positive
    k tests whether it leads. A factor whose whole signal sits at negative k is
    describing the past, not predicting the future.
    """
    common = scores.columns.intersection(period_returns.columns)
    out = {}
    for k in range(-max_lag, max_lag + 1):
        shifted = period_returns[common].shift(-k)
        correlations = [
            scores[c].corr(shifted[c]) for c in common
            if scores[c].notna().sum() > 12 and shifted[c].notna().sum() > 12
        ]
        out[k] = float(np.nanmean(correlations)) if correlations else np.nan
    return pd.Series(out, name="lead_lag_corr").rename_axis("lag_months")


# ---------------------------------------------------------------------------
# Sample splitting and robustness
# ---------------------------------------------------------------------------


def split_sample(index: pd.Index, split_date: str):
    """Split an index into an in-sample design window and a held-out window."""
    cut = pd.Timestamp(split_date)
    stamps = index.to_timestamp() if isinstance(index, pd.PeriodIndex) else pd.DatetimeIndex(index)
    return index[stamps < cut], index[stamps >= cut]


def sensitivity_grid(
    build_scores,
    daily_returns: pd.DataFrame,
    grid: dict,
    freq: str = "ME",
    mode: str = "long_short",
    top_n: int = 5,
    cost_bps: float = 15.0,
) -> pd.DataFrame:
    """Backtest every combination in ``grid`` and report Sharpe / APY / IC.

    ``build_scores(**params) -> DataFrame`` supplies the factor for each cell.
    The point is not to find the best cell — it is to see whether the surface is
    a plateau (robust) or a spike (fitted).
    """
    from itertools import product

    keys = list(grid)
    rows = {}
    period_returns = compound_returns(daily_returns, freq=freq)

    for combination in product(*(grid[k] for k in keys)):
        params = dict(zip(keys, combination))
        try:
            scores = build_scores(**params)
        except Exception as error:                       # noqa: BLE001 — report, don't abort the sweep
            rows[str(params)] = {"error": str(error)[:60]}
            continue

        weights = scores_to_weights(scores, mode=mode, top_n=top_n, bottom_n=top_n)
        result = run_backtest(weights, daily_returns, cost_bps=cost_bps)
        stats_row = performance_stats(result.net_returns, turnover=result.turnover)
        ic_row = ic_summary(rank_ic(scores, period_returns.shift(-1)))
        rows[str(params)] = {
            **{k: params[k] for k in keys},
            "sharpe": stats_row.get("sharpe"),
            "apy": stats_row.get("apy"),
            "max_drawdown": stats_row.get("max_drawdown"),
            "ic_mean": ic_row.get("ic_mean"),
            "ic_t_stat_nw": ic_row.get("ic_t_stat_nw"),
            "annual_turnover": stats_row.get("annual_turnover"),
        }

    return pd.DataFrame(rows).T


def deflated_sharpe(
    observed_sharpe: float,
    n_trials: int,
    n_observations: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    trial_sharpe_std: float = 1.0,
) -> dict:
    """Bailey & Lopez de Prado's haircut for selection bias.

    Testing N configurations and reporting the best one inflates the Sharpe you
    see. This computes the Sharpe the best of N *random* strategies would be
    expected to show, and the probability the observed one beats that.

    ``trial_sharpe_std`` is the dispersion of Sharpe ratios actually observed
    across the trials, and it scales the whole benchmark. Leaving it at 1.0
    assumes trials as varied as unit-normal draws, which for a tight parameter
    sweep massively overstates the hurdle — pass the real cross-trial standard
    deviation.
    """
    if n_trials < 2 or n_observations < 10:
        return {}

    euler = 0.5772156649
    # Expected maximum Sharpe from N independent draws of a zero-Sharpe strategy.
    expected_max = trial_sharpe_std * (
        (1 - euler) * stats.norm.ppf(1 - 1.0 / n_trials)
        + euler * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    )

    denominator = np.sqrt(
        1.0 - skew * observed_sharpe + (kurtosis - 1.0) / 4.0 * observed_sharpe ** 2
    )
    if denominator <= 0:
        return {}
    z = (observed_sharpe - expected_max) * np.sqrt(n_observations - 1) / denominator

    return {
        "observed_sharpe": observed_sharpe,
        "expected_max_sharpe_under_null": float(expected_max),
        "deflated_sharpe_probability": float(stats.norm.cdf(z)),
        "n_trials": n_trials,
    }


def permutation_test(
    scores: pd.DataFrame,
    period_returns: pd.DataFrame,
    n_permutations: int = 500,
    seed: int = 20260731,
) -> dict:
    """Shuffle the score cross-section within each period and re-measure the IC.

    This destroys the mapping between industry and score while preserving both
    the score distribution and every return property — cross-sectional
    dispersion, autocorrelation, the lot. If the real IC does not stand out
    against the shuffled distribution, the signal is not about industries.
    """
    rng = np.random.default_rng(seed)
    forward = period_returns.shift(-1)
    observed = float(rank_ic(scores, forward).mean())

    null = np.empty(n_permutations)
    values = scores.values
    for i in range(n_permutations):
        shuffled = values.copy()
        for row in range(shuffled.shape[0]):
            finite = np.flatnonzero(~np.isnan(shuffled[row]))
            if len(finite) > 1:
                shuffled[row, finite] = shuffled[row, rng.permutation(finite)]
        permuted = pd.DataFrame(shuffled, index=scores.index, columns=scores.columns)
        null[i] = rank_ic(permuted, forward).mean()

    # Two-sided: the neglect hypothesis predicts a negative IC, so magnitude is
    # what we test.
    p_value = float((np.abs(null) >= abs(observed)).mean())
    return {
        "observed_ic": observed,
        "null_ic_mean": float(np.mean(null)),
        "null_ic_std": float(np.std(null)),
        "p_value": p_value,
        "n_permutations": n_permutations,
    }


def bootstrap_sharpe(returns: pd.Series, n_samples: int = 2000, block: int = 21,
                     seed: int = 20260731) -> dict:
    """Stationary block bootstrap confidence interval for the Sharpe ratio.

    Blocks preserve the short-run autocorrelation and volatility clustering that
    an i.i.d. bootstrap would destroy and that a Sharpe ratio is sensitive to.
    """
    values = returns.dropna().values
    if len(values) < block * 5:
        return {}

    rng = np.random.default_rng(seed)
    n = len(values)
    n_blocks = int(np.ceil(n / block))
    sharpes = np.empty(n_samples)

    for i in range(n_samples):
        starts = rng.integers(0, n - block, size=n_blocks)
        sample = np.concatenate([values[s: s + block] for s in starts])[:n]
        std = sample.std()
        sharpes[i] = sample.mean() / std * np.sqrt(252) if std > 0 else 0.0

    std = values.std()
    return {
        "sharpe": float(values.mean() / std * np.sqrt(252)) if std > 0 else np.nan,
        "ci_5": float(np.percentile(sharpes, 5)),
        "ci_95": float(np.percentile(sharpes, 95)),
        "p_sharpe_le_zero": float((sharpes <= 0).mean()),
    }
