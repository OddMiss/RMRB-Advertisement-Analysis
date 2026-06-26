import pandas as pd
import numpy as np

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