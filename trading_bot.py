#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 25 19:10:48 2023

@author: camaike
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
from oandapyV20.contrib.requests import MarketOrderRequest
from oanda_candles import Pair, Gran, CandleClient
from oandapyV20.contrib.requests import TakeProfitDetails, StopLossDetails
import yfinance as yf
import pandas as pd
import datetime
import json

access_token = 'token'
accountID = "id"  # Your account ID here
client = API(access_token)

def calculate_sma(data, period):
    return data['Close'].rolling(window=period).mean()

def signal_generator(df, short_period, long_period):
    df = df.copy()
    df['Short_SMA'] = calculate_sma(df, short_period)
    df['Long_SMA'] = calculate_sma(df, long_period)

    signal = []
    signal.append(0)

    for i in range(1, len(df)):
        if df['Short_SMA'].iloc[i] > df['Long_SMA'].iloc[i] and df['Short_SMA'].iloc[i-1] < df['Long_SMA'].iloc[i-1]:
            signal.append(1)  # Bullish Signal
        elif df['Short_SMA'].iloc[i] < df['Long_SMA'].iloc[i] and df['Short_SMA'].iloc[i-1] > df['Long_SMA'].iloc[i-1]:
            signal.append(2)  # Bearish Signal
        else:
            signal.append(0)  # No Signal

    df['Signal'] = signal
    return df

'''
def download_data(last_days):
    end_date = datetime.datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.datetime.today() - datetime.timedelta(days=last_days)).strftime('%Y-%m-%d')
    ticker_symbol = 'GBPCAD=X'  # Replace with the desired stock symbol
    data = yf.download(ticker_symbol, start=start_date, end=end_date, interval='1h')
    
    return data

d = signal_generator(download_data(4), 9, 20)
d.head(200)
'''

def get_candles(n):
    try:
        client = CandleClient(access_token, real=False)
        print("Connected to the API successfully!")
    except:
        print('Connection to API failed')
        sys.exit(1) 
        
    collector = client.get_collector(Pair.GBP_CAD, Gran.M5)
    candles = collector.grab(n)
    return candles

def trading_job():
    print(f'Job started at {datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")}, execution pending...')
    candles = get_candles(30)
    dfstream = pd.DataFrame(columns=['Open', 'Close', 'High', 'Low'])

    i = 0
    for candle in candles:
        dfstream.loc[i, ['Open']] = float(str(candle.bid.o))
        dfstream.loc[i, ['Close']] = float(str(candle.bid.c))
        dfstream.loc[i, ['High']] = float(str(candle.bid.h))
        dfstream.loc[i, ['Low']] = float(str(candle.bid.l))
        i += 1

    dfstream['Open'] = dfstream['Open'].astype(float)
    dfstream['Close'] = dfstream['Close'].astype(float)
    dfstream['High'] = dfstream['High'].astype(float)
    dfstream['Low'] = dfstream['Low'].astype(float)

    signal_df = signal_generator(dfstream.iloc[:-1, :], 9, 20)
    signal = signal_df['Signal'].iloc[-1]

    previous_candleR = abs(dfstream['High'].iloc[-2] - dfstream['Low'].iloc[-2])

    SLBuy = float(str(candle.bid.o)) - 0.0008  # 5 pips as Stop Loss
    SLSell = float(str(candle.bid.o)) + 0.0008  # 5 pips as Stop Loss

    TPBuy = float(str(candle.bid.o)) + 0.0080  # 50 pips as Take Profit
    TPSell = float(str(candle.bid.o)) - 0.0080  # 50 pips as Take Profit

    if signal == 1:
        print('buy market order executed')
        print(f'TP Buy: {TPBuy}\nSL Buy: {SLBuy}')
        mo = MarketOrderRequest(instrument="GBP_CAD", units=1000, takeProfitOnFill=TakeProfitDetails(price=TPBuy).data, stopLossOnFill=StopLossDetails(price=SLBuy).data)
        r = orders.OrderCreate(accountID, data=mo.data)
        rv = client.request(r)
        print(json.dumps(rv, indent=4))
    elif signal == 2:
        print('sell market order executed')
        print(f'TP Sell: {TPSell}\nSL Sell: {SLSell}')
        mo = MarketOrderRequest(instrument="GBP_CAD", units=-1000, takeProfitOnFill=TakeProfitDetails(price=TPSell).data, stopLossOnFill=StopLossDetails(price=SLSell).data)
        r = orders.OrderCreate(accountID, data=mo.data)
        rv = client.request(r)
        print(json.dumps(rv, indent=4))

    print("Job executed successfully!\n================================")
    
#trading_job()
scheduler = BlockingScheduler()
scheduler.add_job(trading_job, 'interval', minutes=5)
scheduler.start()