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
import sendgrid
import os
from sendgrid.helpers.mail import Mail, Email, To, Content

access_token = ''
#2c0dac5d047d822efd0d4058af8b1973-b8b1e17acd17fb9bddd0b53adae9ae5f'

accountID = ''
#101-004-26226167-002' # Your account ID here
# 101-004-26226167-002
sendgrid_api_key = ''
#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'

client = API(access_token)

def trigger_email(message_body, ticker, timeframe):
    sg = sendgrid.SendGridAPIClient(sendgrid_api_key)
    from_email = Email("chimaroke.amaike@gmail.com")  # Change to your verified sender
    to_email = To("chimamails@gmail.com")  # Change to your recipient
    subject = f"TradingBot Alert of {ticker} on {timeframe} timeframe"
    content = Content("text/plain", message_body)
    mail = Mail(from_email, to_email, subject, content)

    # Get a JSON-ready representation of the Mail object
    mail_json = mail.get()

    # Send an HTTP POST request to /mail/send
    response = sg.client.mail.send.post(request_body=mail_json)

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
        
    collector = client.get_collector(Pair.GBP_CAD, Gran.H1)
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

    SLBuy = float(str(candle.bid.o)) - 0.0005  # 5 pips as Stop Loss
    SLSell = float(str(candle.bid.o)) + 0.0005  # 5 pips as Stop Loss

    TPBuy = float(str(candle.bid.o)) + 0.0050  # 50 pips as Take Profit
    TPSell = float(str(candle.bid.o)) - 0.0050  # 50 pips as Take Profit

    if signal == 1:
        mo = MarketOrderRequest(instrument="GBP_CAD", units=10000, takeProfitOnFill=TakeProfitDetails(price=TPBuy).data, stopLossOnFill=StopLossDetails(price=SLBuy).data)
        r = orders.OrderCreate(accountID, data=mo.data)
        rv = client.request(r)
        order_details = json.dumps(rv, indent=4)
        
        message_body = f'buy market order executed\nTP Buy: {TPBuy}\nSL Buy: {SLBuy}\n{order_details}'
        print(message_body)
        trigger_email(message_body, "GBP_CAD", 'H1')
        
    elif signal == 2:
        message_body = f'buy market order executed\nTP Sell: {TPSell}\nSL Sell: {SLSell}\n{order_details}'
        print(message_body)
        trigger_email(message_body, "GBP_CAD", 'H1')

        mo = MarketOrderRequest(instrument="GBP_CAD", units=-10000, takeProfitOnFill=TakeProfitDetails(price=TPSell).data, stopLossOnFill=StopLossDetails(price=SLSell).data)
        r = orders.OrderCreate(accountID, data=mo.data)
        rv = client.request(r)
        print(json.dumps(rv, indent=4))

    print("Job executed successfully!\n==================================")
    
#trading_job()
scheduler = BlockingScheduler()
scheduler.add_job(trading_job, 'cron', day_of_week='mon-fri', hour='00-23', minute='1', start_date='2023-10-30 00:01:00', timezone='Europe/London')
scheduler.start()
trigger_email('Scheduler running', "GBP_CAD", 'H1')