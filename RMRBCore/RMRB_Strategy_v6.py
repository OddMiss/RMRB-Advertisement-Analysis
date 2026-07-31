"""
RMRB_Strategy_v6
================
The strategy registry: each entry turns the RMRB ad panels plus market data into
a matrix of target weights, one row per rebalance period.

Every strategy here states the economic hypothesis it is betting on. That is not
decoration — it is the thing that decides whether a backtest result is worth
believing. A rule with no mechanism behind it is a curve fit waiting to be found.

    from RMRBCore.RMRB_Strategy_v6 import STRATEGIES, StrategyContext
    ctx = StrategyContext.build(dataset)
    weights = STRATEGIES["neglect_premium"].build(ctx)

``Daily_Z_Score_SoV`` below is the original v6 signal, kept unchanged because
``RMRB_Quant.py`` imports it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from RMRBCore import RMRB_Factor_v6 as F


def Daily_Z_Score_SoV(industry_count_df, trading_days):
    """
    Calculate the Daily Z-Score Share of Voice (SoV) for each industry.

    Parameters:
    - industry_count_df: DataFrame with industries as columns and dates as index, containing daily counts.
    - trading_days: List or DatetimeIndex of trading days to filter the final output.

    Returns:
    - signal_df: DataFrame with the same shape as industry_count_df, containing signals based on Z-Scores.
    - signal_df_2: DataFrame containing the raw Z-Scores for each industry. (Why need this? Because signal_df contains only -1, 0, 1 signals, while signal_df_2 contains the actual continuous Z-Scores for further analysis.)
    """
    # Strategy: Daily Z-Score SoV
    # Define your window size 'n'
    n = 30  # Example: Last 30 days including today

    # Calculate the Numerator: Rolling sum for each industry
    # min_periods=1 ensures you get values for the first few days (before n days have passed)
    # If you want strictly 'NaN' until day n, remove min_periods=1
    industry_rolling_sum = industry_count_df.rolling(window=n, min_periods=1).sum()

    # Calculate the Denominator: Total sum of all industries for that window
    # We sum across the columns (axis=1) for each day
    total_rolling_sum = industry_rolling_sum.sum(axis=1)

    # Calculate SOV: Divide each industry's rolling sum by the total
    # axis=0 aligns the division by the index (date)
    sov_daily_df = industry_rolling_sum.div(total_rolling_sum, axis=0)

    # Cleanup: Handle division by zero
    # If a specific window had 0 total activity, the result is NaN. We fill it with 0.
    sov_daily_df = sov_daily_df.fillna(0)

    rolling_window = sov_daily_df.rolling(window=365, min_periods=365)
    rolling_mean = rolling_window.mean()
    rolling_std = rolling_window.std()

    # Calculate Z-score safely, replacing 0 standard deviation with NaN to prevent division-by-zero
    sov_z_score_daily_df = (sov_daily_df - rolling_mean) / rolling_std.replace(0, np.nan)

    # Clean up NaNs (converts the first 29 buffer days and division-by-zero occurrences to 0.0)
    sov_z_score_daily_df = sov_z_score_daily_df.fillna(0.0)

    # Set all sov_z_score_all_df values to larger or equal than 2 to 1 (otherwise 0)
    # Define conditions and choices
    # 🚨 --- CRUCIAL STEP: Filter Z-Scores down to Trading Days only ---
    # This drops weekends and holidays, preserving the accumulated weekend paper effects inside Monday's row.
    sov_z_score_trading_df = sov_z_score_daily_df.reindex(trading_days)
    signal_df = sov_z_score_trading_df.copy()
    conditions = [
        (signal_df <= -2.0),   # Condition for 1
        (signal_df >= 2.0)   # Condition for -1
    ]
    choices = [1, -1]

    # Create new DataFrame using select
    # default=0 handles the "Otherwise 0" case
    signal_df = pd.DataFrame(
        np.select(conditions, choices, default=0),
        index=signal_df.index,
        columns=signal_df.columns
    )
    output = {'signal_df': signal_df, "signal_df_2": sov_z_score_trading_df}
    return output


# ===========================================================================
# Strategy framework
# ===========================================================================


@dataclass
class StrategyContext:
    """Everything a strategy needs, computed once and shared across the registry."""

    panels: dict                       # panel name -> daily industry frame
    macro: pd.DataFrame                # daily market-wide ad series
    daily_returns: pd.DataFrame        # daily industry returns
    freq: str = "ME"

    period_returns: pd.DataFrame = field(default=None)
    attention: dict = field(default=None)          # build_attention_factor output
    commercial: dict = field(default=None)
    public: dict = field(default=None)

    ts_window: int = 12
    min_activity: float = 0.5
    deseason: bool = True

    @classmethod
    def build(cls, panels: dict, daily_returns: pd.DataFrame, freq: str = "ME",
              ts_window: int = 12, min_activity: float = 0.5, deseason: bool = True):
        """Align the ad panels to the industries that actually have price data."""
        tradable = [c for c in panels["count_all"].columns if c in daily_returns.columns]
        panels = {name: frame[tradable] if name != "macro" else frame
                  for name, frame in panels.items()}

        ctx = cls(
            panels=panels, macro=panels["macro"], daily_returns=daily_returns[tradable],
            freq=freq, ts_window=ts_window, min_activity=min_activity, deseason=deseason,
        )
        ctx.period_returns = F.compound_returns(ctx.daily_returns, freq)

        common = dict(freq=freq, ts_window=ts_window, ts_min_periods=ts_window,
                      deseason=deseason, min_activity=min_activity)
        ctx.attention = F.build_attention_factor(panels["count_all"], **common)
        ctx.commercial = F.build_attention_factor(panels["count_commercial"], **common)
        ctx.public = F.build_attention_factor(
            panels["count_public"], **{**common, "min_activity": min_activity * 0.6}
        )
        return ctx

    def momentum(self, lookback: int = 1, skip: int = 0) -> pd.DataFrame:
        """Momentum restricted to the same active universe as the attention factor."""
        raw = F.momentum(self.daily_returns, freq=self.freq, lookback=lookback, skip=skip)
        return raw.where(self.attention["mask"])


@dataclass
class Strategy:
    name: str
    hypothesis: str
    builder: object
    mode: str = "long_only"            # how the pipeline should size it
    holding_periods: int = 1

    def build(self, ctx: StrategyContext) -> pd.DataFrame:
        return self.builder(ctx)


STRATEGIES: dict = {}


def register(name: str, hypothesis: str, mode: str = "long_only", holding_periods: int = 1):
    def wrap(func):
        STRATEGIES[name] = Strategy(name, hypothesis, func, mode, holding_periods)
        return func
    return wrap


def _equal_weight(selection_mask: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight the True cells of a boolean frame, row by row."""
    counts = selection_mask.sum(axis=1)
    weights = selection_mask.astype(float).div(counts.replace(0, np.nan), axis=0)
    return weights.fillna(0.0)


# ---------------------------------------------------------------------------
# Score-producing strategies (the pipeline turns these into weights)
# ---------------------------------------------------------------------------


@register(
    "neglect_premium",
    "State-media attention is a lagging, contrarian indicator. By the time the "
    "People's Daily is carrying a sector's ads, the move is already priced and "
    "the marginal buyer has arrived; sectors the paper has gone quiet on are "
    "where the un-narrated repricing happens. Long low attention, short high.",
    mode="score", holding_periods=3,
)
def neglect_premium(ctx: StrategyContext) -> pd.DataFrame:
    return -ctx.attention["score"]


@register(
    "commercial_spend_climax",
    "Restricted to paid commercial ads, which are a direct read on a sector's "
    "marketing budget. Discretionary ad spend peaks when managers are most "
    "confident — historically a late-cycle tell, in the same family as the "
    "magazine-cover and equity-issuance indicators. Fade the spenders.",
    mode="score", holding_periods=3,
)
def commercial_spend_climax(ctx: StrategyContext) -> pd.DataFrame:
    return -ctx.commercial["score"]


@register(
    "policy_attention",
    "Public-service and policy ads are the propaganda agenda rather than a "
    "corporate media buy, so the mechanism is the opposite one: sustained "
    "official attention flags where state support is heading. Tested long, at a "
    "longer horizon than the commercial channel.",
    mode="score", holding_periods=6,
)
def policy_attention(ctx: StrategyContext) -> pd.DataFrame:
    return ctx.public["score"]


@register(
    "silent_winner",
    "The neglect premium is conditional on price context. A quiet sector that is "
    "already rallying is information arbitrage — capital is moving before the "
    "narrative arrives. A loud sector that is falling is the opposite: state "
    "media reassurance into a decline. Blend neglect with 1-month momentum.",
    mode="score", holding_periods=3,
)
def silent_winner(ctx: StrategyContext) -> pd.DataFrame:
    neglect = -ctx.attention["score"]
    mom = F.cross_sectional_standardise(ctx.momentum(lookback=1), "rank")
    return F.combine({"neglect": neglect, "momentum": mom},
                     {"neglect": 0.5, "momentum": 0.5})


@register(
    "neglect_ex_momentum",
    "The same neglect signal with cross-sectional momentum regressed out, to "
    "test whether the ad data carries anything the price series does not "
    "already contain.",
    mode="score", holding_periods=3,
)
def neglect_ex_momentum(ctx: StrategyContext) -> pd.DataFrame:
    neglect = -ctx.attention["score"]
    mom = F.cross_sectional_standardise(ctx.momentum(lookback=1), "rank")
    return F.orthogonalise(neglect, {"momentum": mom})


# ---------------------------------------------------------------------------
# Weight-producing strategies (they define their own portfolio construction)
# ---------------------------------------------------------------------------


@register(
    "hype_avoidance",
    "The quintile ladder says nearly all of the effect is in the loudest "
    "bucket underperforming, not the quietest outperforming. So express it the "
    "cheap way: hold the equal-weight sector basket and simply drop sectors "
    "that have had an attention spike in the last few months. Rare events mean "
    "low turnover, which is the binding constraint on this signal.",
    mode="weights", holding_periods=1,
)
def hype_avoidance(ctx: StrategyContext, threshold: float = 2.0, memory: int = 3) -> pd.DataFrame:
    z, mask = ctx.attention["zscore"], ctx.attention["mask"]
    active = mask.fillna(False)
    recently_hyped = (z >= threshold).rolling(memory, min_periods=1).max().fillna(0.0) > 0
    keep = active & ~recently_hyped
    # Never let the screen empty the book — fall back to the full active set.
    too_thin = keep.sum(axis=1) < 8
    keep.loc[too_thin] = active.loc[too_thin]
    keep.loc[active.sum(axis=1) < 12] = False
    return _equal_weight(keep)


@register(
    "equal_weight_active",
    "Control portfolio, not a strategy: the equal-weight basket of whatever "
    "sectors pass the activity mask on the day. Every attention strategy has to "
    "beat this before its ranking is worth anything.",
    mode="weights", holding_periods=1,
)
def equal_weight_active(ctx: StrategyContext) -> pd.DataFrame:
    active = ctx.attention["mask"].fillna(False)
    active.loc[active.sum(axis=1) < 12] = False
    return _equal_weight(active)


# ---------------------------------------------------------------------------
# Market-wide timing overlay
# ---------------------------------------------------------------------------


def macro_timing_exposure(
    ctx: StrategyContext,
    column: str = "area_commercial",
    window: int = 36,
    min_periods: int = 24,
    deseason: bool = True,
    floor: float = 0.5,
    cap: float = 1.5,
    slope: float = 0.5,
) -> pd.Series:
    """Target gross exposure from aggregate advertising intensity.

    Hypothesis: total commercial ad spend in the party paper is a procyclical
    corporate-confidence gauge, so a spending climax should mark exuberance and a
    drought capitulation — a market-level contrarian timing signal.

    ``deseason`` is not a tuning knob, it is the control that decides whether the
    signal is real. RMRB ad volume is violently seasonal (December and March run
    four times February) and A-share returns have their own calendar, so the raw
    z-score picks up the two calendars agreeing rather than any information.
    Leave it on unless you are deliberately reproducing the naive version.
    """
    monthly = ctx.macro[column].resample(ctx.freq).sum()
    if deseason:
        monthly = F.deseasonalise(monthly.to_frame("x"))["x"]
    rolling = monthly.rolling(window=window, min_periods=min_periods)
    z = (monthly - rolling.mean()) / (rolling.std() + 1e-8)
    return (1.0 - slope * z).clip(lower=floor, upper=cap).rename("target_exposure")


def apply_timing_overlay(weights: pd.DataFrame, exposure: pd.Series) -> pd.DataFrame:
    """Scale a weight matrix period by period by a target gross exposure."""
    scale = exposure.reindex(weights.index).ffill().fillna(1.0)
    return weights.mul(scale, axis=0)
