"""
RMRB_Factor_v6
==============
Turns the raw daily ad panels from :mod:`RMRB_Dataset_v6` into cross-sectional
factor scores that a portfolio can actually be built from.

The four problems this layer solves
-----------------------------------
**1. Level bias.** Total ad volume in the People's Daily trends and swings with
the ad market. Raw counts therefore mix "this sector got more attention" with
"the paper sold more ads". Dividing by the day's total — Share of Voice — makes
the panel a genuine *composition* series.

**2. Structural bias.** This is the failure diagnosed in `Industry-Analysis.ipynb`:
banks are covered every month and cosmetics essentially never, so a raw
cross-sectional sort on SoV just re-selects the same permanently-quiet sectors
forever, and the strategy becomes an accidental small-cap beta bet. The fix is
to z-score *within each industry against its own history* before comparing
industries to one another.

**3. Calendar bias.** RMRB ad flow is strongly seasonal — Spring Festival
brand campaigns, the March Two Sessions policy block, National Day, the
December ad-budget flush. Undetrended, a "spike" in March is mostly a calendar
artefact. We remove a month-of-year effect estimated on strictly trailing data.

**4. Thin-data noise.** A sector averaging 0.1 ads a month produces a z-score
driven entirely by whether a single ad happened to run. Those observations are
masked out rather than traded.

No-lookahead discipline
-----------------------
Every rolling statistic here is trailing-only, and the de-seasonalisation uses
an expanding mean that is explicitly shifted by one occurrence. The factor
computed with data through period ``t`` is meant to be traded at the start of
``t+1``; the shift that enforces that lives in the backtest layer, not here, so
that diagnostics can align factor(t) against return(t+k) for any k.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------


def to_period(daily: pd.DataFrame, freq: str = "ME", how: str = "sum") -> pd.DataFrame:
    """Aggregate a daily panel to a coarser frequency.

    Ad counts are summed (an ad on a Saturday still counts toward the month);
    returns are compounded. Weekend and holiday papers stay in the sample —
    dropping them would silently discard roughly a third of the ad flow.
    """
    if how == "compound":
        return (1.0 + daily).resample(freq).prod() - 1.0
    resampler = daily.resample(freq)
    if how == "sum":
        return resampler.sum()
    if how == "mean":
        return resampler.mean()
    if how == "last":
        return resampler.last()
    raise ValueError(f"Unknown aggregation: {how}")


def compound_returns(daily_returns: pd.DataFrame, freq: str = "ME") -> pd.DataFrame:
    """Compound daily returns into period returns."""
    return (1.0 + daily_returns).resample(freq).prod() - 1.0


# ---------------------------------------------------------------------------
# Normalisation primitives
# ---------------------------------------------------------------------------


def share_of_voice(counts: pd.DataFrame) -> pd.DataFrame:
    """Row-normalise a count panel into shares that sum to 1 per period.

    Periods with no ads at all become 0 rather than NaN — "the paper carried no
    ads" is information, not a missing observation.
    """
    total = counts.sum(axis=1)
    return counts.div(total.replace(0.0, np.nan), axis=0).fillna(0.0)


def deseasonalise(panel: pd.DataFrame, freq_per_year: int = 12) -> pd.DataFrame:
    """Strip a calendar effect using only past occurrences of the same month.

    For each column and each period ``t`` we subtract the expanding mean of that
    column over *previous* periods sharing ``t``'s month-of-year. Early
    observations have no history to lean on and are left untouched, which is the
    honest choice: we simply do not know the seasonal yet.
    """
    if freq_per_year != 12:
        return panel

    season = panel.index.month
    adjusted = panel.copy()
    for month in range(1, 13):
        mask = season == month
        if mask.sum() < 2:
            continue
        block = panel.loc[mask]
        # shift(1) => the mean excludes the current observation.
        seasonal_mean = block.expanding(min_periods=1).mean().shift(1)
        adjusted.loc[mask] = (block - seasonal_mean.fillna(0.0)).values
    return adjusted


def timeseries_zscore(
    panel: pd.DataFrame,
    window: int = 12,
    min_periods: int = 12,
    eps: float = 1e-8,
) -> pd.DataFrame:
    """Z-score each column against its own trailing history.

    This is the industry-neutralisation step. After it, "-2" means *this sector
    is unusually quiet for itself*, which is comparable across sectors in a way
    that a raw share never is.
    """
    rolling = panel.rolling(window=window, min_periods=min_periods)
    mean = rolling.mean()
    std = rolling.std()
    return (panel - mean) / (std + eps)


def activity_mask(
    counts: pd.DataFrame,
    window: int = 12,
    min_periods: int = 12,
    min_mean: float = 0.5,
) -> pd.DataFrame:
    """True where a sector has carried enough ad flow for a z-score to mean anything.

    ``min_mean`` is in ads per period. At the monthly frequency, 0.5 means the
    sector has averaged at least one ad every two months over the trailing year.
    """
    trailing_mean = counts.rolling(window=window, min_periods=min_periods).mean()
    return trailing_mean >= min_mean


def winsorise(panel: pd.DataFrame, limit: float = 3.0) -> pd.DataFrame:
    """Clip extreme scores. A single freak month should tilt a portfolio, not own it."""
    return panel.clip(lower=-limit, upper=limit)


def cross_sectional_standardise(panel: pd.DataFrame, method: str = "rank") -> pd.DataFrame:
    """Put every period's cross-section on a common scale.

    ``rank``   -> uniform on [-0.5, 0.5]; robust, ignores the magnitude of outliers.
    ``zscore`` -> demeaned and unit-variance within the period; keeps magnitudes.
    ``demean`` -> demeaned only; use when the raw units are already meaningful.

    All three produce a zero-mean cross-section, which is what makes a
    long-short book naturally market-neutral in weight terms.
    """
    if method == "rank":
        ranks = panel.rank(axis=1, pct=True)
        return ranks.sub(0.5)
    if method == "zscore":
        mean = panel.mean(axis=1)
        std = panel.std(axis=1)
        return panel.sub(mean, axis=0).div(std.replace(0.0, np.nan), axis=0)
    if method == "demean":
        return panel.sub(panel.mean(axis=1), axis=0)
    raise ValueError(f"Unknown cross-sectional method: {method}")


# ---------------------------------------------------------------------------
# The attention factor
# ---------------------------------------------------------------------------


def build_attention_factor(
    daily_counts: pd.DataFrame,
    freq: str = "ME",
    ts_window: int = 12,
    ts_min_periods: int = 12,
    deseason: bool = True,
    min_activity: float = 0.5,
    winsor: float = 3.0,
    cs_method: str = "rank",
    sign: float = 1.0,
) -> dict:
    """Full attention-factor pipeline: counts -> tradable cross-sectional score.

    Pipeline: resample -> Share of Voice -> de-seasonalise -> trailing z-score
    -> activity mask -> winsorise -> cross-sectional standardise.

    ``sign`` flips the factor. The neglect hypothesis says low attention predicts
    high returns, so a contrarian score uses ``sign=-1``.

    Returns the intermediate frames as well as the final score, because the
    diagnostics in :mod:`RMRB_Research_v6` want to inspect each stage.
    """
    period_counts = to_period(daily_counts, freq=freq, how="sum")
    sov = share_of_voice(period_counts)
    sov_adj = deseasonalise(sov) if deseason else sov

    zscore = timeseries_zscore(sov_adj, window=ts_window, min_periods=ts_min_periods)
    mask = activity_mask(period_counts, window=ts_window,
                         min_periods=ts_min_periods, min_mean=min_activity)
    zscore = zscore.where(mask)

    score = cross_sectional_standardise(winsorise(zscore, winsor), method=cs_method) * sign

    return {
        "counts": period_counts,
        "sov": sov,
        "sov_deseasonalised": sov_adj,
        "zscore": zscore,
        "mask": mask,
        "score": score,
    }


# ---------------------------------------------------------------------------
# Control / companion factors
# ---------------------------------------------------------------------------


def momentum(
    daily_returns: pd.DataFrame,
    freq: str = "ME",
    lookback: int = 1,
    skip: int = 0,
) -> pd.DataFrame:
    """Trailing price momentum over ``lookback`` periods, optionally skipping the
    most recent ``skip`` periods to sidestep short-term reversal."""
    period_returns = compound_returns(daily_returns, freq=freq)
    log_returns = np.log1p(period_returns)
    trailing = log_returns.rolling(window=lookback, min_periods=lookback).sum()
    return np.expm1(trailing.shift(skip))


def realised_volatility(daily_returns: pd.DataFrame, freq: str = "ME", window: int = 60) -> pd.DataFrame:
    """Annualised trailing realised volatility, sampled at period ends."""
    vol = daily_returns.rolling(window=window, min_periods=window // 2).std() * np.sqrt(252)
    return vol.resample(freq).last()


def orthogonalise(factor: pd.DataFrame, controls: dict) -> pd.DataFrame:
    """Cross-sectional residual of ``factor`` after regressing out ``controls``.

    Run period by period: ``factor ~ 1 + controls``, keep the residual. If the
    RMRB score still predicts returns after momentum and volatility are removed,
    the alternative data is carrying information the price series does not.
    """
    residual = pd.DataFrame(np.nan, index=factor.index, columns=factor.columns)

    for period in factor.index:
        y = factor.loc[period]
        frame = {"__y__": y}
        for name, control in controls.items():
            if period in control.index:
                frame[name] = control.loc[period]
        block = pd.DataFrame(frame).dropna()
        if len(block) < len(frame) + 2:      # need more observations than regressors
            continue

        target = block.pop("__y__").values
        design = np.column_stack([np.ones(len(block)), block.values])
        try:
            beta, *_ = np.linalg.lstsq(design, target, rcond=None)
        except np.linalg.LinAlgError:
            continue
        residual.loc[period, block.index] = target - design @ beta

    return residual


def combine(factors: dict, weights: dict = None, cs_method: str = "zscore") -> pd.DataFrame:
    """Blend several standardised factors into one score.

    Each input is re-standardised cross-sectionally first, so a factor with a
    wider natural spread cannot dominate the blend by accident.
    """
    weights = weights or {name: 1.0 for name in factors}
    total = sum(abs(w) for w in weights.values()) or 1.0

    stacked = None
    for name, frame in factors.items():
        piece = cross_sectional_standardise(frame, method=cs_method) * (weights.get(name, 0.0) / total)
        stacked = piece if stacked is None else stacked.add(piece, fill_value=0.0)
    return stacked


# ---------------------------------------------------------------------------
# Market-wide (timing) signal
# ---------------------------------------------------------------------------


def macro_ad_intensity(
    macro: pd.DataFrame,
    freq: str = "ME",
    column: str = "area_commercial",
    window: int = 36,
    min_periods: int = 24,
) -> pd.Series:
    """Aggregate commercial ad volume, z-scored against its own trailing history.

    The economic reading: corporate marketing budgets are procyclical and
    discretionary. When companies collectively buy a lot of expensive
    front-of-book newspaper space, corporate confidence — and usually the
    market's own risk appetite — is running hot. Both tails are interesting: a
    spending climax has historically marked exuberance, a spending drought
    marks capitulation.
    """
    monthly = macro[column].resample(freq).sum()
    rolling = monthly.rolling(window=window, min_periods=min_periods)
    return (monthly - rolling.mean()) / (rolling.std() + 1e-8)
