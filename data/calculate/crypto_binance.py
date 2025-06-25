import pandas as pd
import time
from utils.flows.fetch_calculate_insert import fetch_calculate_and_insert, update_technical_indicators
from utils.calculation.indicators import calculate_ema, calculate_supertrend, calculate_spike, detect_large_gap, calculate_average_volume, calculate_exponential_regression
from utils.calculation.supertrend import faster_supertrend
from utils.calculation.slope_r2 import calculate_exponential_regression_optimized
from utils.calculation.optimized_indicators import calculate_spike_optimized, detect_large_gap_optimized, calculate_average_volume_optimized, calculate_sustained_volume_spike
from dotenv import load_dotenv
from data.fetch.indian_equity import fetch_symbol_list_indian_equity
from finstore.finstore import Finstore
import os
import traceback
from utils.db.batch import BatchInserter
from tqdm import tqdm

# Load environment variables from .env file
load_dotenv(dotenv_path='config/.env')

# Access the DATABASE_PATH environment variable
database_path = os.getenv('DATABASE_PATH')

def calculate_technical_indicators(market_name, symbol_list, timeframe='1d'):
    '''
    One time run function for calculating all custom indicators for a given market.
    Calculates and saves the indicator results into database.
    '''
    try:
        finstore = Finstore(market_name=market_name, timeframe=timeframe, enable_append=True)
        ohlcv_data = finstore.read.symbol_list(symbol_list=symbol_list)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_ema, length=100)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_ema, length=200)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=faster_supertrend, period=7, multiplier=3)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_exponential_regression_optimized, window=90)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_exponential_regression_optimized, window=30)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_exponential_regression_optimized, window=15)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_spike_optimized, lookback_period=30, spike_threshold=0.85)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=detect_large_gap_optimized, lookback_period=30, gap_threshold=0.15)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_average_volume_optimized, lookback_period=90)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_sustained_volume_spike, lookback_period=50, spike_duration=3, threshold=5) 
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_sustained_volume_spike, lookback_period=50, spike_duration=3, threshold=10)   
    except Exception as e:
        print(f"Error calculating technical indicators: {e}")
        print(f"Full traceback:")
        print(traceback.format_exc())

def update_calculated_indicators(market_name='crypto_binance', symbol_list=[], all_entries=True, timeframe='4h', data_lookback_period=500, pair='BTC'):
    
    '''
    Update the calculated indicators for the given market, symbols, and timeframe. Ideal for running everyday to update the indicators for new data.
    To update indicators for a large number of dates, adjust data_lookback_period to a higher value.
    
    Parameters:
    - market_name (str): The market name (e.g., 'indian_equity').
    - symbol_list (list): List of symbols to update indicators for (e.g., ['SBIN', 'HDFC']).
    - timeframe (str): The timeframe for OHLCV data (e.g., '1d').
    - data_lookback_period (int): Number of past data points to consider for recalculating the indicators (default: 500).
    '''
    
    if not symbol_list:
        symbol_list = fetch_symbol_list_indian_equity(complete_list=all_entries)
    
    try:
        finstore = Finstore(market_name=market_name, timeframe=timeframe, enable_append=True, limit_data_lookback=data_lookback_period, pair=pair)
        ohlcv_data = finstore.read.symbol_list(symbol_list=symbol_list)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_ema, length=100)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_ema, length=200)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=faster_supertrend, period=7, multiplier=3)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_exponential_regression_optimized, window=90)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_exponential_regression_optimized, window=30)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_exponential_regression_optimized, window=15)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_spike_optimized, lookback_period=30, spike_threshold=0.85)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=detect_large_gap_optimized, lookback_period=30, gap_threshold=0.15)
        finstore.write.indicator(ohlcv_data=ohlcv_data, calculation_func=calculate_average_volume_optimized, lookback_period=90)
    except Exception as e:
        print(f"Error updating technical indicators: {e}")
        print(f"Full traceback:")
        print(traceback.format_exc())


if __name__ == "__main__":
    _start = time.time()
    #calculate_technical_indicators(market_name='indian_equity', start_timestamp=None, all_entries=True, symbol_list=None, timeframe='1d')
    symbol_list = ['COLPAL.NS', 'KAYNES.NS', '^NSEI']
    update_calculated_indicators(market_name='indian_equity', symbol_list=symbol_list, timeframe='1d', all_entries=False)
    _end_time = time.time()
    print(f"Time taken: {_end_time - _start} seconds")
