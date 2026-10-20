"""
RMRB_Backtest_v6
================
A daily, weight-drifting portfolio simulator plus the performance statistics
used to judge it.

Design decisions that matter for whether the numbers are believable
-------------------------------------------------------------------
**Execution lag is explicit and defaults to one period.** The People's Daily is
on the street before the 09:30 open, so a same-day trade is *physically*
possible. It is not, however, what this engine assumes by default. A factor
built from data through month-end M is executed at the close of the first
trading day of M+1 (``execution_lag=1`` trading day after the rebalance date).
Assuming you can act on a signal at the very instant it becomes complete is the
single most common way a backtest manufactures returns that do not exist.

**Weights drift between rebalances.** Holding a portfolio does not keep it
equal-weighted; winners grow. Re-imposing equal weights every day would book a
free daily rebalancing bonus and understate turnover. The engine lets weights
drift with realised returns and only trades on rebalance dates, so the fee
charged is the fee a real desk would pay.

**Turnover is measured against drifted weights.** Fees are levied on the gap
between the target and what you actually still hold, not against the previous
target.

**Costs are charged on both legs.** ``cost_bps`` is one-way. A 15 bp default is
realistic for A-share sector ETFs (commission + a slice of spread + impact);
sector index futures would be cheaper, single-stock baskets much dearer. The
research layer runs a sensitivity sweep over this, because a strategy that only
works at zero cost is not a strategy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE = 0.02


# ---------------------------------------------------------------------------
# Weight construction
# ---------------------------------------------------------------------------


def scores_to_weights(
    scores: pd.DataFrame,
    mode: str = "long_short",
    top_n: int = 5,
    bottom_n: int = 5,
    gross_leverage: float = 1.0,
    min_names: int = 6,
) -> pd.DataFrame:
    """Convert cross-sectional scores into target weights, one row per rebalance.

    ``long_only``   -> equal weight across the ``top_n`` highest scores.
    ``long_short``  -> equal weight long the top ``top_n``, short the bottom
                       ``bottom_n``; each leg carries half the gross, so the book
                       is dollar-neutral.
    ``rank_weight`` -> weight proportional to the demeaned score, normalised to
                       ``gross_leverage``. Uses the whole cross-section and so is
                       less exposed to the arbitrary choice of ``top_n``.

    Rows with fewer than ``min_names`` scored industries produce an all-cash
    target: early in the sample the trailing windows have not filled and the
    cross-section is too thin to sort meaningfully.
    """
    weights = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)

    for period in scores.index:
        row = scores.loc[period].dropna()
        if len(row) < min_names:
            continue

        if mode == "rank_weight":
            centred = row - row.mean()
            scale = centred.abs().sum()
            if scale <= 0:
                continue
            weights.loc[period, centred.index] = centred / scale * gross_leverage
            continue

        n_long = min(top_n, len(row) // 2)
        if n_long < 1:
            continue
        longs = row.nlargest(n_long).index

        if mode == "long_only":
            weights.loc[period, longs] = gross_leverage / n_long
        elif mode == "long_short":
            n_short = min(bottom_n, len(row) // 2)
            shorts = row.nsmallest(n_short).index
            weights.loc[period, longs] = 0.5 * gross_leverage / n_long
            weights.loc[period, shorts] = -0.5 * gross_leverage / n_short
        else:
            raise ValueError(f"Unknown weighting mode: {mode}")

    return weights


def stagger_tranches(weights: pd.DataFrame, holding_periods: int = 1) -> pd.DataFrame:
    """Spread each rebalance across overlapping tranches of ``holding_periods``.

    Instead of replacing the whole book every month, deploy 1/H of capital each
    month and hold each slice for H months. This is the standard overlapping-
    portfolio construction: it cuts turnover by roughly H, damps the influence of
    any single entry date, and — where the event study says the effect takes
    several months to play out — matches the holding period to the horizon over
    which the alpha actually accrues.
    """
    if holding_periods <= 1:
        return weights
    stacked = sum(weights.shift(lag).fillna(0.0) for lag in range(holding_periods))
    return stacked / holding_periods


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


@dataclass
class BacktestResult:
    gross_returns: pd.Series
    net_returns: pd.Series
    equity: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series
    exposure: pd.Series

    @property
    def drawdown(self) -> pd.Series:
        peak = self.equity.cummax()
        return self.equity / peak - 1.0


def run_backtest(
    target_weights: pd.DataFrame,
    daily_returns: pd.DataFrame,
    cost_bps: float = 15.0,
    execution_lag: int = 1,
    max_turnover: float = None,
) -> BacktestResult:
    """Simulate a portfolio day by day.

    ``target_weights`` is indexed by rebalance period (month-end labels are
    fine); each row is executed on the first trading day of the *following*
    period, then delayed a further ``execution_lag`` trading days.

    ``max_turnover`` optionally caps how far the book may move on any single
    rebalance, by shrinking the trade toward the current holdings. Real mandates
    have such caps and they materially change the cost profile of a fast signal.
    """
    trading_days = daily_returns.index
    industries = daily_returns.columns
    n = len(industries)
    one_way_cost = cost_bps / 10_000.0

    # Map each target row onto the trading day it is executed on.
    day_series = pd.Series(trading_days, index=trading_days)
    first_day_of_month = day_series.groupby(day_series.dt.to_period("M")).first()

    schedule = {}
    for period in target_weights.index:
        signal_month = pd.Period(period, freq="M") if not isinstance(period, pd.Period) else period
        execute_month = signal_month + 1
        if execute_month not in first_day_of_month.index:
            continue
        execution_day = first_day_of_month.loc[execute_month]
        if execution_lag:
            position = trading_days.get_loc(execution_day) + execution_lag
            if position >= len(trading_days):
                continue
            execution_day = trading_days[position]
        schedule[execution_day] = period

    aligned_targets = target_weights.reindex(columns=industries).fillna(0.0)
    returns_matrix = daily_returns.values

    held = np.zeros(n)
    weights_log = np.zeros((len(trading_days), n))
    gross = np.zeros(len(trading_days))
    cost_log = np.zeros(len(trading_days))
    turnover_log = np.zeros(len(trading_days))

    for i, date in enumerate(trading_days):
        if date in schedule:
            target = aligned_targets.loc[schedule[date]].values.astype(float)
            trade = target - held
            requested = np.abs(trade).sum() / 2.0
            if max_turnover is not None and requested > max_turnover > 0:
                trade *= max_turnover / requested
                target = held + trade
            turnover_log[i] = np.abs(trade).sum() / 2.0
            cost_log[i] = np.abs(trade).sum() * one_way_cost
            held = target

        weights_log[i] = held
        day_returns = returns_matrix[i]
        portfolio_return = float(held @ day_returns)
        gross[i] = portfolio_return

        # Drift. Each position grows at its own return while NAV grows at the
        # portfolio return, so w_i' = w_i(1+r_i) / (1+r_p). Gross exposure is
        # deliberately left to move on its own between rebalances — re-imposing
        # a fixed gross every day would be an untraded, unpriced rebalance.
        nav_growth = 1.0 + portfolio_return
        if nav_growth > 1e-8:
            held = held * (1.0 + day_returns) / nav_growth
        else:
            held = np.zeros(n)

    gross_series = pd.Series(gross, index=trading_days, name="gross")
    cost_series = pd.Series(cost_log, index=trading_days, name="cost")
    net_series = (gross_series - cost_series).rename("net")
    weights_frame = pd.DataFrame(weights_log, index=trading_days, columns=industries)

    return BacktestResult(
        gross_returns=gross_series,
        net_returns=net_series,
        equity=(1.0 + net_series).cumprod().rename("equity"),
        weights=weights_frame,
        turnover=pd.Series(turnover_log, index=trading_days, name="turnover"),
        costs=cost_series,
        exposure=weights_frame.abs().sum(axis=1).rename("gross_exposure"),
    )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def newey_west_tstat(series: pd.Series, lags: int = None) -> float:
    """t-statistic of the mean, robust to autocorrelation and heteroskedasticity.

    Overlapping holding periods induce serial correlation in the return series,
    which inflates a naive t-stat. Newey-West with a Bartlett kernel is the
    standard correction; the default lag follows the usual ``4(T/100)^(2/9)``.
    """
    values = series.dropna().values
    T = len(values)
    if T < 10:
        return np.nan
    if lags is None:
        lags = int(np.floor(4 * (T / 100.0) ** (2.0 / 9.0)))

    demeaned = values - values.mean()
    variance = float(demeaned @ demeaned) / T
    for lag in range(1, min(lags, T - 1) + 1):
        cov = float(demeaned[lag:] @ demeaned[:-lag]) / T
        variance += 2.0 * (1.0 - lag / (lags + 1.0)) * cov
    if variance <= 0:
        return np.nan
    return values.mean() / np.sqrt(variance / T)


def performance_stats(
    returns: pd.Series,
    benchmark: pd.Series = None,
    risk_free: float = DEFAULT_RISK_FREE,
    turnover: pd.Series = None,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> dict:
    """Standard performance panel for a daily return series."""
    returns = returns.dropna()
    if returns.empty:
        return {}

    n = len(returns)
    equity = (1.0 + returns).cumprod()
    total = float(equity.iloc[-1] - 1.0)
    years = n / periods_per_year
    apy = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else np.nan
    vol = float(returns.std() * np.sqrt(periods_per_year))

    excess_daily = returns - risk_free / periods_per_year
    sharpe = float(excess_daily.mean() / returns.std() * np.sqrt(periods_per_year)) if returns.std() else np.nan

    downside = returns[returns < 0.0]
    downside_vol = float(downside.std() * np.sqrt(periods_per_year)) if len(downside) > 1 else np.nan
    sortino = float((apy - risk_free) / downside_vol) if downside_vol and downside_vol > 0 else np.nan

    drawdown = equity / equity.cummax() - 1.0
    max_dd = float(drawdown.min())
    calmar = float(apy / abs(max_dd)) if max_dd < 0 else np.nan

    stats = {
        "total_return": total,
        "apy": apy,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "hit_rate": float((returns > 0).mean()),
        "skew": float(returns.skew()),
        "t_stat_nw": float(newey_west_tstat(returns)),
        "n_days": n,
    }

    if turnover is not None:
        annual_turnover = float(turnover.sum() / years) if years > 0 else np.nan
        stats["annual_turnover"] = annual_turnover

    if benchmark is not None:
        bench = benchmark.reindex(returns.index).fillna(0.0)
        bench_var = float(bench.var())
        beta = float(returns.cov(bench) / bench_var) if bench_var > 0 else np.nan
        bench_equity = (1.0 + bench).cumprod()
        bench_apy = float(bench_equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else np.nan
        active = returns - bench
        tracking_error = float(active.std() * np.sqrt(periods_per_year))
        stats.update({
            "beta": beta,
            "alpha_annual": float(apy - (risk_free + beta * (bench_apy - risk_free))) if not np.isnan(beta) else np.nan,
            "excess_apy": float(apy - bench_apy),
            "tracking_error": tracking_error,
            "information_ratio": float((apy - bench_apy) / tracking_error) if tracking_error > 0 else np.nan,
            "t_stat_active_nw": float(newey_west_tstat(active)),
        })

    return stats


def stats_table(rows: dict, columns: list = None) -> pd.DataFrame:
    """Assemble ``{name: stats_dict}`` into a tidy, printable frame."""
    frame = pd.DataFrame(rows).T
    preferred = columns or [
        "apy", "volatility", "sharpe", "sortino", "max_drawdown", "calmar",
        "excess_apy", "information_ratio", "alpha_annual", "beta",
        "t_stat_nw", "annual_turnover", "hit_rate",
    ]
    ordered = [c for c in preferred if c in frame.columns]
    return frame[ordered + [c for c in frame.columns if c not in ordered]]


def format_stats_table(frame: pd.DataFrame) -> str:
    """Render a stats table with percentages where percentages belong."""
    percent_columns = {
        "apy", "volatility", "max_drawdown", "excess_apy", "alpha_annual",
        "hit_rate", "total_return", "tracking_error",
    }
    def render(value, style):
        if pd.isna(value):
            return "—"
        if not isinstance(value, (int, float, np.number)):
            return str(value)          # e.g. the per-strategy start date
        if style == "percent":
            return f"{value:.2%}"
        if style == "count":
            return f"{value:,.0f}"
        return f"{value:.2f}"

    display = frame.copy()
    for column in display.columns:
        style = ("percent" if column in percent_columns
                 else "count" if column == "n_days" else "ratio")
        display[column] = display[column].map(lambda v, s=style: render(v, s))
    return display.to_string()
