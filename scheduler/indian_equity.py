'''
This is the main file for the Indian Equity pipeline.
Run as a module to start the pipeline.
python -m scheduler.indian_equity
'''

from data.update.indian_equity import fill_gap
from data.fetch.indian_equity import fetch_symbol_list_indian_equity
from utils.db.fetch import fetch_entries
from executor.indian_equity_pipeline import run_pipeline
import pandas as pd
import schedule
import time
from executor.executor import execute_trades_telegram, execute_trades_zerodha, is_market_open, get_balance
from utils.notifier.telegram import send_telegram_message
from utils.data.dataframe import get_top_symbols_by_average_volume
import pytz
from datetime import datetime, timedelta
import os

def pipeline(sim_start):
    print("Pipeline started")
    
    fill_gap(market_name='indian_equity', timeframe='1d', complete_list=True)
    try: 
        symbol_list = fetch_symbol_list_indian_equity(index_name='nse_eq_symbols')
        ohlcv_data = fetch_entries(market_name='indian_equity', timeframe='1d', all_entries=True)
        print(ohlcv_data['SBIN.NS']['timestamp'].max())
        
        sim_end = pd.Timestamp.now().strftime('%Y-%m-%d 00:00:00')
        fresh_buys, fresh_sells = run_pipeline(ohlcv_data, sim_start, sim_end, complete_list=False, symbol_list=symbol_list, weekday=2, init_cash=30000)
    except Exception as e:
        print(e)
    
    # Save fresh buys and sells to parquet files
    if not fresh_buys.empty:
        fresh_buys.to_parquet('database/db/fresh_buys.parquet')
    if not fresh_sells.empty:
        fresh_sells.to_parquet('database/db/fresh_sells.parquet')

def execute_trades():
    '''
    This function executes the trades for the day.
    '''

    if not is_market_open():
        send_telegram_message('Market is closed for today. Skipping trade execution.')
        return

    if not os.path.exists('database/db/fresh_buys.parquet') and not os.path.exists('database/db/fresh_sells.parquet'):
        send_telegram_message('No fresh trades to execute. Skipping trade execution.')
        return

    # Load fresh buys and sells if files exist
    if os.path.exists('database/db/fresh_sells.parquet'):
        fresh_sells = pd.read_parquet('database/db/fresh_sells.parquet')
        execute_trades_telegram(fresh_sells)
        successful_trades_sell, failed_trades_sell = execute_trades_zerodha(fresh_sells)
        
        # Save failed trades
        if failed_trades_sell:
            pd.DataFrame(failed_trades_sell).to_parquet('database/db/failed_sells.parquet')
        
        # Remove fresh sells file regardless of trade success
        os.remove('database/db/fresh_sells.parquet')

    if os.path.exists('database/db/fresh_buys.parquet'):
        fresh_buys = pd.read_parquet('database/db/fresh_buys.parquet')
        execute_trades_telegram(fresh_buys)
        successful_trades, failed_trades = execute_trades_zerodha(fresh_buys)
        
        # Save failed trades
        if failed_trades:
            pd.DataFrame(failed_trades).to_parquet('database/db/failed_buys.parquet')
        
        # Remove fresh buys file regardless of trade success
        os.remove('database/db/fresh_buys.parquet')
    

def retry_failed_trades():

    # Retry failed sells (similar to failed buys)
    if os.path.exists('database/db/failed_sells.parquet'):
        failed_sells = pd.read_parquet('database/db/failed_sells.parquet')
        failed_sells_formatted = failed_sells.apply(lambda x: {
            'Column': x['symbol'],
            'Side': x['side'],
            'Size': x['size'],
            'Price': x['price']
        }, axis=1).tolist()
        
        execute_trades_telegram(pd.DataFrame(failed_sells_formatted))
        successful_trades_sell, still_failed_trades_sell = execute_trades_zerodha(pd.DataFrame(failed_sells_formatted))
        
        if still_failed_trades_sell:
            pd.DataFrame(still_failed_trades_sell).to_parquet('database/db/failed_sells.parquet')
        else:
            os.remove('database/db/failed_sells.parquet')
            
    # Retry failed buys
    if os.path.exists('database/db/failed_buys.parquet'):
        failed_buys = pd.read_parquet('database/db/failed_buys.parquet')
        # Convert failed trades back to the format expected by execute_trades_zerodha
        failed_buys_formatted = failed_buys.apply(lambda x: {
            'Column': x['symbol'],
            'Side': x['side'],
            'Size': x['size'],
            'Price': x['price']
        }, axis=1).tolist()
        
        execute_trades_telegram(pd.DataFrame(failed_buys_formatted))
        successful_trades, still_failed_trades = execute_trades_zerodha(pd.DataFrame(failed_buys_formatted))
        
        if still_failed_trades:
            pd.DataFrame(still_failed_trades).to_parquet('database/db/failed_buys.parquet')
        else:
            os.remove('database/db/failed_buys.parquet')
    
def balance_and_holdings():
    portfolio_message = get_balance()
    send_telegram_message(portfolio_message)

def Scheduler(sim_start):
    '''
    Scheduler function that runs the pipeline every day at 6 pm IST to get fresh orders and sells from pipeline.
    '''
    ist = pytz.timezone('Asia/Kolkata')
    utc = pytz.UTC

    # Schedule pipeline at 7 PM IST
    target_time_ist_pipeline = datetime.now(ist).replace(hour=19, minute=0, second=0, microsecond=0)
    target_time_utc_pipeline = target_time_ist_pipeline.astimezone(utc).time()
    schedule.every().day.at(target_time_utc_pipeline.strftime('%H:%M')).do(pipeline, sim_start)

    # Schedule pipeline at 5 PM IST
    target_time_ist_pipeline = datetime.now(ist).replace(hour=17, minute=0, second=0, microsecond=0)
    target_time_utc_pipeline = target_time_ist_pipeline.astimezone(utc).time()
    schedule.every().day.at(target_time_utc_pipeline.strftime('%H:%M')).do(balance_and_holdings)

    # Schedule trade execution at 9:01 AM IST
    target_time_ist_execute = datetime.now(ist).replace(hour=9, minute=15, second=0, microsecond=0)
    target_time_utc_execute = target_time_ist_execute.astimezone(utc).time()
    schedule.every().day.at(target_time_utc_execute.strftime('%H:%M')).do(execute_trades)

    # Schedule retry of failed trades at 12 PM IST
    target_time_ist_retry = datetime.now(ist).replace(hour=12, minute=0, second=0, microsecond=0)
    target_time_utc_retry = target_time_ist_retry.astimezone(utc).time()
    schedule.every().day.at(target_time_utc_retry.strftime('%H:%M')).do(retry_failed_trades)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    sim_start = pd.Timestamp.now() - pd.Timedelta(days=6)
    Scheduler(sim_start)
    #pipeline(sim_start)