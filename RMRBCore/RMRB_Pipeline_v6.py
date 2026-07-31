"""
RMRB_Pipeline_v6
================
End-to-end runner: raw ad archive -> panels -> factor diagnostics -> backtests
-> robustness checks -> report.

    python RMRBCore/RMRB_Pipeline_v6.py                  # full study, SW level 1
    python RMRBCore/RMRB_Pipeline_v6.py --level 2        # SW level-2 breadth test
    python RMRBCore/RMRB_Pipeline_v6.py --rebuild        # re-extract from JSON
    python RMRBCore/RMRB_Pipeline_v6.py --stage factor   # one stage only
    python RMRBCore/RMRB_Pipeline_v6.py --figures        # also write PNGs

Stages run in order and each prints its own section, so the console output is
the report. Tables are also written to ``Output/`` as CSV.

The stage order is deliberate. Diagnostics come before backtests because an
equity curve is uninterpretable until you know whether the factor has a
monotone ladder and a stable IC; robustness comes after because it prices the
search that produced the winner.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from RMRBCore.RMRB_Dataset_v6 import RMRBDataset
from RMRBCore import RMRB_Backtest_v6 as B
from RMRBCore import RMRB_Factor_v6 as F
from RMRBCore import RMRB_Research_v6 as R
from RMRBCore import RMRB_Strategy_v6 as S

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")
OUTPUT_DIR = f"{REPO_ROOT}/Output/"

#: Split date for the held-out window. Chosen once, before any strategy was
#: tuned, at roughly two-thirds of the sample.
OOS_SPLIT = "2021-01-01"

#: One-way cost in basis points. A-share sector ETFs: commission plus a slice of
#: spread and impact. Deliberately not optimistic.
COST_BPS = 15.0


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {text}")
    print("=" * 78)


def save(frame: pd.DataFrame, name: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    frame.to_csv(f"{OUTPUT_DIR}{name}.csv", encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def stage_data(args) -> dict:
    banner("STAGE 1 — DATA")
    dataset = RMRBDataset(level=args.level)
    panels = dataset.build_panels(rebuild=args.rebuild, verbose=False)
    market = dataset.load_market()
    dataset.report_diagnostics(panels)

    returns = market["industry_roi"]
    tradable = [c for c in panels["count_all"].columns if c in returns.columns]
    print(f"Tradable industries: {len(tradable)} of {len(panels['count_all'].columns)}")
    print(f"Price history      : {returns.index[0].date()} -> {returns.index[-1].date()} "
          f"({len(returns):,} trading days)")

    context = S.StrategyContext.build(panels, returns)
    return {"dataset": dataset, "panels": panels, "market": market, "ctx": context}


def stage_factor(state: dict) -> dict:
    """Does the factor carry information at all, and over what horizon?"""
    banner("STAGE 2 — FACTOR DIAGNOSTICS")
    ctx = state["ctx"]
    period_returns = ctx.period_returns
    forward = period_returns.shift(-1)

    print("\n-- Rank IC by panel (score = raw attention; negative IC favours contrarian) --")
    rows = {}
    for panel in ("count_all", "count_commercial", "count_public",
                  "area_commercial", "prominence_commercial", "count_legacy"):
        if panel not in ctx.panels:
            continue
        built = F.build_attention_factor(
            ctx.panels[panel], freq=ctx.freq, ts_window=ctx.ts_window,
            ts_min_periods=ctx.ts_window, deseason=ctx.deseason,
            min_activity=ctx.min_activity,
        )
        summary = R.ic_summary(R.rank_ic(built["score"], forward))
        names = built["score"].notna().sum(axis=1)
        summary["avg_names"] = float(names[names > 0].mean())
        rows[panel] = summary
    ic_table = pd.DataFrame(rows).T
    print(ic_table.round(4).to_string())
    save(ic_table, "factor_ic_by_panel")

    score = -ctx.attention["score"]        # contrarian orientation from here on

    print("\n-- Horizon scan (contrarian score vs cumulative return over t+1..t+h) --")
    horizons = R.horizon_scan(score, period_returns, horizons=range(1, 13))
    print(horizons[["ic_mean", "ic_ir", "ic_t_stat_nw", "n_periods"]].round(4).to_string())
    save(horizons, "factor_horizon_scan")

    print("\n-- Quintile ladder (equal-weight portfolio return by score bucket, % per month) --")
    ladder = R.quantile_portfolios(score, period_returns, n_quantiles=5)
    if ladder:
        print((ladder["mean_returns"] * 100).round(3).to_string())
        print(f"monotonicity (Spearman rho across buckets): {ladder['monotonicity_rho']:+.2f}")
        print(f"Q5-Q1 spread Newey-West t-stat            : {ladder['spread_t_stat_nw']:+.2f}")
        save(ladder["periodic_returns"], "factor_quantile_returns")

    print("\n-- Lead-lag: is coverage an echo of the past or a lead on the future? --")
    print(R.lead_lag(ctx.attention["zscore"], period_returns, max_lag=6).round(4).to_string())

    print("\n-- Event study: cumulative abnormal return around |z| >= 1.5 shocks --")
    events = R.event_study(ctx.attention["zscore"], period_returns, threshold=1.5, pre=3, post=9)
    if "car_neglect" in events and "car_hype" in events:
        car = pd.DataFrame({"neglect": events["car_neglect"], "hype": events["car_hype"],
                            "spread": events["car_spread"]})
        print((car * 100).round(2).to_string())
        print(f"n_neglect={events['n_neglect']}  n_hype={events['n_hype']}  "
              f"T+9 spread t={events.get('spread_t_stat', float('nan')):+.2f} "
              f"(p={events.get('spread_p_value', float('nan')):.3f})")
        save(car, "factor_event_study")

    print("\n-- In-sample / out-of-sample stability of the contrarian IC --")
    in_sample, out_sample = R.split_sample(score.index, OOS_SPLIT)
    split_rows = {
        "full": R.ic_summary(R.rank_ic(score, forward)),
        f"IS (< {OOS_SPLIT})": R.ic_summary(R.rank_ic(score.loc[in_sample], forward)),
        f"OOS (>= {OOS_SPLIT})": R.ic_summary(R.rank_ic(score.loc[out_sample], forward)),
    }
    split_table = pd.DataFrame(split_rows).T
    print(split_table.round(4).to_string())
    save(split_table, "factor_is_oos_ic")

    state["score"] = score
    state["forward"] = forward
    return state


def stage_backtest(state: dict, args) -> dict:
    """Turn every registered strategy into a portfolio and price it honestly."""
    banner("STAGE 3 — STRATEGY BACKTESTS")
    ctx = state["ctx"]
    returns = ctx.daily_returns
    equal_weight = returns.mean(axis=1)

    results, rows = {}, {}
    for name, strategy in S.STRATEGIES.items():
        built = strategy.build(ctx)
        if strategy.mode == "score":
            variants = {
                f"{name} [LO top8]": B.scores_to_weights(built, "long_only", top_n=8),
                f"{name} [LS top6]": B.scores_to_weights(built, "long_short", top_n=6, bottom_n=6),
            }
        else:
            variants = {name: built}

        for label, weights in variants.items():
            weights = B.stagger_tranches(weights, strategy.holding_periods)
            result = B.run_backtest(weights, returns, cost_bps=COST_BPS)

            invested = result.exposure[result.exposure > 1e-9]
            if invested.empty:
                continue
            # Every strategy has a different warm-up. Judge each one from the day
            # it is first invested, against a benchmark clipped to the same day —
            # otherwise a long warm-up sitting in cash masquerades as a result.
            start = invested.index[0]
            net = result.net_returns.loc[start:]
            benchmark = equal_weight.loc[start:] if "LS" not in label else None
            stats = B.performance_stats(net, benchmark=benchmark,
                                        turnover=result.turnover.loc[start:])
            stats["start"] = start.date()
            rows[label] = stats
            results[label] = result

    rows["BENCHMARK equal-weight"] = B.performance_stats(equal_weight)
    for column in state["market"]["benchmark_roi"].columns:
        rows[f"BENCHMARK {column}"] = B.performance_stats(state["market"]["benchmark_roi"][column])

    table = B.stats_table(rows)
    print(B.format_stats_table(table))
    save(table, "strategy_performance")

    print("\n-- Macro timing overlay on the equal-weight active basket --")
    base = S.STRATEGIES["equal_weight_active"].build(ctx)
    overlay_rows = {}
    for label, deseason in (("raw z (no seasonal control)", False),
                            ("de-seasonalised z", True)):
        exposure = S.macro_timing_exposure(ctx, deseason=deseason)
        weights = S.apply_timing_overlay(base, exposure)
        result = B.run_backtest(weights, returns, cost_bps=COST_BPS)
        invested = result.exposure[result.exposure > 1e-9]
        if invested.empty:
            continue
        start = invested.index[0]
        overlay_rows[label] = B.performance_stats(
            result.net_returns.loc[start:], benchmark=equal_weight.loc[start:],
            turnover=result.turnover.loc[start:],
        )
    if overlay_rows:
        overlay_table = B.stats_table(overlay_rows)
        print(B.format_stats_table(overlay_table))
        save(overlay_table, "macro_timing_overlay")

    state["results"] = results
    return state


def stage_robustness(state: dict) -> dict:
    """Price the search: does the finding survive costs, parameters and shuffling?"""
    banner("STAGE 4 — ROBUSTNESS")
    ctx = state["ctx"]
    returns = ctx.daily_returns
    score = state["score"]

    print("\n-- Transaction-cost sensitivity (neglect long-short, top 6, 3-month tranches) --")
    weights = B.stagger_tranches(B.scores_to_weights(score, "long_short", 6, 6), 3)
    cost_rows = {}
    for cost in (0.0, 5.0, 10.0, 15.0, 20.0, 30.0):
        result = B.run_backtest(weights, returns, cost_bps=cost)
        invested = result.exposure[result.exposure > 1e-9]
        start = invested.index[0]
        cost_rows[f"{cost:.0f} bp"] = B.performance_stats(
            result.net_returns.loc[start:], turnover=result.turnover.loc[start:]
        )
    cost_table = B.stats_table(cost_rows, columns=["apy", "sharpe", "t_stat_nw",
                                                   "max_drawdown", "annual_turnover"])
    print(B.format_stats_table(cost_table))
    save(cost_table, "robustness_cost_sensitivity")

    print("\n-- Parameter sensitivity (is the surface a plateau or a spike?) --")
    panel = ctx.panels["count_all"]

    def build_scores(ts_window, min_activity, deseason):
        built = F.build_attention_factor(
            panel, freq=ctx.freq, ts_window=ts_window, ts_min_periods=ts_window,
            deseason=deseason, min_activity=min_activity,
        )
        return -built["score"]

    grid = R.sensitivity_grid(
        build_scores, returns,
        grid={"ts_window": [12, 18, 24], "min_activity": [0.3, 0.5, 1.0],
              "deseason": [True, False]},
        cost_bps=COST_BPS,
    )
    numeric = grid[["ts_window", "min_activity", "deseason", "ic_mean",
                    "ic_t_stat_nw", "sharpe", "apy"]].astype({"ic_mean": float})
    print(numeric.to_string(index=False))
    save(grid, "robustness_parameter_grid")
    positive = (grid["ic_mean"].astype(float) > 0).mean()
    print(f"\nShare of parameter cells with the hypothesised (positive contrarian) IC sign: "
          f"{positive:.0%} of {len(grid)}")

    print("\n-- Permutation test: shuffle the score cross-section within each month --")
    permutation = R.permutation_test(score, ctx.period_returns, n_permutations=300)
    for key, value in permutation.items():
        print(f"  {key:22s}: {value:.4f}" if isinstance(value, float) else f"  {key:22s}: {value}")

    print("\n-- Deflated Sharpe: haircut for the number of configurations tried --")
    result = B.run_backtest(weights, returns, cost_bps=COST_BPS)
    invested = result.exposure[result.exposure > 1e-9]
    net = result.net_returns.loc[invested.index[0]:]
    observed = B.performance_stats(net)["sharpe"]
    n_trials = max(len(grid), 2) * 6            # grid cells x weighting variants tried
    trial_std = float(pd.to_numeric(grid["sharpe"], errors="coerce").std())
    deflated = R.deflated_sharpe(observed, n_trials=n_trials, n_observations=len(net),
                                 skew=float(net.skew()), kurtosis=float(net.kurtosis() + 3.0),
                                 trial_sharpe_std=trial_std if trial_std > 0 else 1.0)
    print(f"  {'observed cross-trial Sharpe std':34s}: {trial_std:.4f}")
    for key, value in deflated.items():
        print(f"  {key:34s}: {value:.4f}" if isinstance(value, float) else f"  {key:34s}: {value}")

    print("\n-- Block bootstrap of the Sharpe ratio --")
    bootstrap = R.bootstrap_sharpe(net)
    for key, value in bootstrap.items():
        print(f"  {key:22s}: {value:+.4f}")

    return state


def stage_figures(state: dict) -> dict:
    banner("STAGE 5 — FIGURES")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ctx = state["ctx"]
    equal_weight = ctx.daily_returns.mean(axis=1)
    results = state.get("results", {})

    # Every curve is rebased to the first day on which any strategy is actually
    # invested. Letting the benchmark compound through the 11-month warm-up
    # would draw a gap the aligned performance table does not contain.
    starts = [r.exposure[r.exposure > 1e-9].index[0] for r in results.values()
              if (r.exposure > 1e-9).any()]
    start = min(starts) if starts else equal_weight.index[0]

    figure, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                gridspec_kw={"height_ratios": [2, 1]})
    shown = [label for label in results if "LS" not in label][:5]
    for label in shown:
        net = results[label].net_returns.loc[start:]
        axes[0].plot((1 + net).cumprod(), linewidth=1.2, label=label)
    axes[0].plot((1 + equal_weight.loc[start:]).cumprod(), color="black", linewidth=1.8,
                 linestyle="--", label="Equal-weight industries")
    axes[0].set_title(f"RMRB attention strategies vs equal-weight sector basket "
                      f"(net of {COST_BPS:.0f} bp, rebased {start.date()})")
    axes[0].set_ylabel("Growth of 1")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[0].grid(alpha=0.3, linestyle=":")

    ic = R.rank_ic(state["score"], ctx.period_returns.shift(-1))
    axes[1].bar(ic.index, ic.values, width=20, alpha=0.5, label="Monthly Rank IC")
    twin = axes[1].twinx()
    twin.plot(ic.index, ic.cumsum(), color="darkorange", linewidth=1.6, label="Cumulative IC")
    axes[1].axhline(0, color="grey", linewidth=0.8)
    axes[1].set_ylabel("Rank IC")
    twin.set_ylabel("Cumulative")
    axes[1].grid(alpha=0.3, linestyle=":")

    figure.tight_layout()
    figure.savefig(f"{OUTPUT_DIR}rmrb_strategy_overview.png", dpi=130)
    print(f"Wrote {OUTPUT_DIR}rmrb_strategy_overview.png")
    return state


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="RMRB advertisement alpha research pipeline")
    parser.add_argument("--level", type=int, default=1, choices=(1, 2),
                        help="Shenwan industry tier for the cross-section")
    parser.add_argument("--rebuild", action="store_true", help="re-extract panels from raw JSON")
    parser.add_argument("--stage", default="all",
                        choices=("all", "data", "factor", "backtest", "robustness"))
    parser.add_argument("--figures", action="store_true", help="also write PNG figures")
    args = parser.parse_args()

    state = stage_data(args)
    if args.stage in ("all", "factor", "backtest", "robustness"):
        state = stage_factor(state)
    if args.stage in ("all", "backtest", "robustness"):
        state = stage_backtest(state, args)
    if args.stage in ("all", "robustness"):
        state = stage_robustness(state)
    if args.figures:
        stage_figures(state)

    banner("DONE")
    print(f"Tables written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
