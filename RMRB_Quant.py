import pandas as pd
import numpy as np
from Config.Config import ETF_DATA_PATH
from RMRBCore.RMRB_Quant_v6 import (
    analyze_factor_performance, plot_cumulative_returns,
    calculate_industry_and_benchmark_metrics
)
from RMRBCore.RMRB_Strategy_v6 import Daily_Z_Score_SoV
from Utils.main import PrintUtils, FileUtils, JsonUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
Dict_to_JsonFile = JsonUtils.Dict_to_JsonFile
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict

Begin_date = "20140201"
End_date = "20251231"

SW_SECTOR_PATH_MAPPING = JsonFile_to_Dict(ETF_DATA_PATH + "SW-SECTOR-PATH-MAPPING.json") # Get the mapping of sector names to their corresponding file paths
BENCHMARK_PATH_MAPPING = JsonFile_to_Dict(ETF_DATA_PATH + "BENCHMARK-PATH-MAPPING.json") # Get the mapping of benchmark names to their corresponding file paths
# Get the list of sector industries and benchmarks from the mapping dictionaries
SW_SECTOR_LEVEL_1_List = [industry for industry in SW_SECTOR_PATH_MAPPING.keys() if len(industry.split('-')) == 1]
BENCHMARK_List = list(BENCHMARK_PATH_MAPPING.keys())

# Pre-compute unified DatetimeIndex objects
start_dt = pd.to_datetime(Begin_date)
end_dt = pd.to_datetime(End_date)
full_date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')

# --- NEW: Extract True Trading Days Calendar ---
# Read the primary benchmark (e.g., HS300) to act as your calendar source of truth
sample_bench_file = BENCHMARK_PATH_MAPPING[BENCHMARK_List[0]]
sample_df = pd.read_csv(ETF_DATA_PATH + sample_bench_file, parse_dates=['date'])
trading_days = sample_df[(sample_df['date'] >= start_dt) & (sample_df['date'] <= end_dt)]['date'].sort_values().unique()
trading_days = pd.DatetimeIndex(trading_days)

data_metric_output = calculate_industry_and_benchmark_metrics(
    ETF_DATA_PATH=ETF_DATA_PATH,
    SW_SECTOR_LEVEL_1_List=SW_SECTOR_LEVEL_1_List,
    SW_SECTOR_PATH_MAPPING=SW_SECTOR_PATH_MAPPING,
    BENCHMARK_List=BENCHMARK_List,
    BENCHMARK_PATH_MAPPING=BENCHMARK_PATH_MAPPING,
    start_dt=start_dt,
    end_dt=end_dt,
    trading_days=trading_days
)

industry_level1_roi_all_df = data_metric_output['industry_level1_roi_all_df']
industry_level1_pnl_all_df = data_metric_output['industry_level1_pnl_all_df']
benchmark_roi_all_df = data_metric_output['benchmark_roi_all_df']
benchmark_pnl_all_df = data_metric_output['benchmark_pnl_all_df']

# Load the saved CSV file
# industry_count_df columns: date (index), industry1, industry2, ..., industryN
# Because People's daily is released every day, the industry_count_df is expected to have a row for each day, 
# with counts of how many times each industry was mentioned in the People's daily on that day.
industry_count_df = pd.read_csv(ETF_DATA_PATH + "AD_Industry_Count_Analysis.csv", parse_dates=['date'], index_col='date')

# =====================================================================
# PRODUCTION UNIFIED STRATEGY: CONDITIONAL DOUBLE-SORT MATRIX TRADING ENGINE
# =====================================================================
# 1. Aggregate daily calendar data to monthly signals
monthly_counts = industry_count_df.resample('ME').sum()
monthly_returns = (1 + industry_level1_roi_all_df).resample('ME').prod() - 1.0

# 2. Extract Share of Voice (SoV) and Apply Column-Wise Neutralization
monthly_total = monthly_counts.sum(axis=1)
monthly_sov = monthly_counts.div(monthly_total, axis=0).fillna(0.0)

rolling_mean = monthly_sov.rolling(window=12, min_periods=12).mean()
rolling_std = monthly_sov.rolling(window=12, min_periods=12).std()
monthly_z_score = ((monthly_sov - rolling_mean) / (rolling_std + 1e-6)).fillna(0.0)

# 3. Apply Dynamic Noise Floor Mask (Requires mean >= 1.0 raw count/month)
rolling_raw_mean = monthly_counts.rolling(window=12, min_periods=12).mean()
active_universe_mask = rolling_raw_mean >= 1.0
neutralized_z_score = monthly_z_score.where(active_universe_mask, np.nan)

# 4. Shift Signal Matrices to Prevent Lookahead Bias
neutralized_z_score.index = neutralized_z_score.index.to_period('M')
monthly_returns.index = monthly_returns.index.to_period('M')

shifted_z_score = neutralized_z_score.shift(1)
shifted_momentum = monthly_returns.shift(1) # Past 1-month return acts as momentum factor

# 5. Initialize Fresh Buy Matrices for Each Alpha Tranche
silent_winners_buys = pd.DataFrame(0.0, index=shifted_z_score.index, columns=shifted_z_score.columns)
fallen_angels_buys  = pd.DataFrame(0.0, index=shifted_z_score.index, columns=shifted_z_score.columns)
tactical_hype_buys  = pd.DataFrame(0.0, index=shifted_z_score.index, columns=shifted_z_score.columns)

# 6. Cross-Sectional Double-Sort Selection Loop
for period in shifted_z_score.index:
    z_row = shifted_z_score.loc[period].dropna()
    mom_row = shifted_momentum.loc[period].reindex(z_row.index).dropna()
    
    # Ensure there are enough valid industries in the cross-section to segment
    if len(z_row) >= 9:
        # Cross-Sectional Tercile Quantizing (Rank-based mapping to bypass identical value crashes)
        z_terciles = pd.qcut(z_row.rank(method='first'), 3, labels=['Low', 'Mid', 'High'])
        mom_terciles = pd.qcut(mom_row.rank(method='first'), 3, labels=['Low', 'Mid', 'High'])
        
        # Quadrant Filtering
        for col in z_row.index:
            z_cat = z_terciles.loc[col]
            mom_cat = mom_terciles.loc[col]
            
            # Strategy A: Silent Winners (Low Media Z-Score + High Price Momentum)
            if z_cat == 'Low' and mom_cat == 'High':
                silent_winners_buys.loc[period, col] = 1.0
                
            # Strategy B: Fallen Angels (Low Media Z-Score + Low Price Momentum)
            elif z_cat == 'Low' and mom_cat == 'Low':
                fallen_angels_buys.loc[period, col] = 1.0
                
            # Strategy C: Tactical Hype (High Media Z-Score + Mid Price Momentum)
            elif z_cat == 'High' and mom_cat == 'Mid':
                tactical_hype_buys.loc[period, col] = 1.0

# =====================================================================
# MODULAR STEP 7 & 8: Generate Composite Monthly Signals
# =====================================================================
# Apply your asymmetric holding periods
active_silent_winners = (silent_winners_buys.rolling(window=5, min_periods=1).sum() > 0).astype(float)
active_fallen_angels  = (fallen_angels_buys.rolling(window=5, min_periods=1).sum() > 0).astype(float)
active_tactical_hype  = (tactical_hype_buys.rolling(window=1, min_periods=1).sum() > 0).astype(float)

# Sum the active matrices. 
# Industries hold integer values representing total active tranche backing.
monthly_signals = active_silent_winners + active_fallen_angels + active_tactical_hype

# =====================================================================
# MODULAR STEP 9: Map to Daily Signal Dataframe
# =====================================================================
daily_signal_df = pd.DataFrame(np.nan, index=trading_days, columns=industry_count_df.columns)

trading_days_series = pd.Series(trading_days, index=trading_days)
first_trading_days = trading_days_series.groupby(trading_days_series.dt.to_period('M')).first()

# FIXED: Reindex the monthly alpha signals before mapping to daily variables
aligned_monthly_signals = monthly_signals.reindex(columns=industry_level1_roi_all_df.columns, fill_value=0.0)

for period, first_day in first_trading_days.items():
    if period in aligned_monthly_signals.index:
        daily_signal_df.loc[first_day] = aligned_monthly_signals.loc[period]

# Your clean, standalone daily signal dataframe
signal_df = daily_signal_df.ffill().fillna(0.0)
print(">>> Signal Generation Complete: signal_df generated successfully.")
# ===================== End of Strategy Formulation =====================

# ===================== Weights, Positions, and Fees Calculation =====================
# CORRECTED STEP 10: PRODUCTION WEIGHT DRIFT & REALISTIC FEE ENGINE
print("\n" + "="*20 + " RUNNING TRUE WEIGHT-DRIFT BACKTEST ENGINE " + "="*20)

# FIXED: Convert signals to weights AND align columns to the market return matrix
monthly_weights = monthly_signals.div(monthly_signals.sum(axis=1), axis=0).fillna(0.0)
monthly_weights = monthly_weights.reindex(columns=industry_level1_roi_all_df.columns, fill_value=0.0)

# 1. Initialize True Execution DataFrames
signal_weight = pd.DataFrame(0.0, index=trading_days, columns=industry_level1_roi_all_df.columns)
signal_fee = pd.DataFrame(0.0, index=trading_days, columns=industry_level1_roi_all_df.columns)
portfolio_gross_roi = pd.Series(0.0, index=trading_days)

# 2. Map the first trading day of each month to its corresponding Period object
rebalance_schedule = {first_day: period for period, first_day in first_trading_days.items()}

# 3. Establish Transaction Fee Parameters
BUY_FEE = 0.001
SELL_FEE = 0.001

current_drifting_weights = np.zeros(len(industry_level1_roi_all_df.columns))

# 4. Chronological Daily Capital Simulation Loop
for date in trading_days:
    daily_market_returns = industry_level1_roi_all_df.loc[date].values
    
    # SYSTEM TRIGGER: It's the first trading day of the month -> Execute Rebalance
    if date in rebalance_schedule:
        current_period = rebalance_schedule[date]
        if current_period in monthly_weights.index:
            target_weights = monthly_weights.loc[current_period].values
            
            # Turnover represents true transactional distance
            weight_changes = target_weights - current_drifting_weights
            
            portfolio_buys = np.clip(weight_changes, 0, None) * BUY_FEE
            portfolio_sells = np.abs(np.clip(weight_changes, None, 0)) * SELL_FEE
            signal_fee.loc[date] = portfolio_buys + portfolio_sells
            
            current_drifting_weights = target_weights

    # Record the active weights that went into today's market session
    signal_weight.loc[date] = current_drifting_weights
    
    # Compute today's true portfolio gross return based on active allocations
    portfolio_gross_roi.loc[date] = np.sum(current_drifting_weights * daily_market_returns)
    
    # --- THE DRIFT MECHANIC ---
    current_drifting_weights = current_drifting_weights * (1.0 + daily_market_returns)
    total_portfolio_wealth = np.sum(current_drifting_weights)
    
    if total_portfolio_wealth > 0.0:
        current_drifting_weights = current_drifting_weights / total_portfolio_wealth
    else:
        current_drifting_weights = np.zeros(len(industry_level1_roi_all_df.columns))

# FIXED: Extracted clean, drifted net returns directly from simulation metrics
portfolio_total_fees = signal_fee.sum(axis=1) 
portfolio_net_roi = portfolio_gross_roi - portfolio_total_fees 
print(">>> True Weight Drift Simulation Complete. Lookahead Bias and Rebalance Illusion Fully Eliminated.")
# ===================== End of Weights, Positions, and Fees Calculation =====================

# ===================== Backtesting and Performance Metrics =====================
# Get benchmark return data
HS_300 = benchmark_roi_all_df["HS300"]
CS_500 = benchmark_roi_all_df["CSI500"]
CS_1000 = benchmark_roi_all_df["CSI1000"]
# Taking the mean across axis=1 averages all industry returns for each day
EW = industry_level1_roi_all_df.mean(axis=1)

# Plot cumulative returns for the portfolio and benchmarks
plot_cumulative_returns(
    portfolio_net_roi=portfolio_net_roi,
    HS_300=HS_300, CS_500=CS_500,
    CS_1000=CS_1000, EW=EW
)

# Analyze factor performance using the signal DataFrame, industry ROI, portfolio net ROI, and benchmark returns
analyze_factor_performance(
    signal_df=signal_df,
    signal_roi_df=industry_level1_roi_all_df,
    portfolio_net_roi=portfolio_net_roi,
    trading_days=trading_days,
    HS_300=HS_300, CS_500=CS_500,
    CS_1000=CS_1000, EW=EW
)
# ===================== End of Backtesting and Performance Metrics =====================