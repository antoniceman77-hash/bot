import os
import time
import threading
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# СЮДА ВСТАВЬТЕ ВАШ ВЕБХУК ДИСКОРДА ВНУТРЬ КАВЫЧЕК
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542130167844044830/gPu0J4ky4g-Arlo1DfqQQK0JDoVdYmlKerDJtwfORw-bp0bOhZML70N4ohM8C1PuwfNf

@app.route('/')
def home():
    return "Бот работает"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url).json()
        return [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=50"
        res = requests.get(url).json()
        klines = res['result']['list']
        
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df = df.astype(float).iloc[::-1].reset_index(drop=True)

        df['ma_fast'] = df['close'].rolling(9).mean()
        df['ma_slow'] = df['close'].rolling(21).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))

        last, prev = df.iloc[-1], df.iloc[-2]
        
        depth_url = f"https://bybit.com{symbol}&limit=25"
        depth_res = requests.get(depth_url).json()
        bids_vol = sum([float(b) for b in depth_res['result']['b']])
        asks_vol = sum([float(a) for a in depth_res['result']['a']])

        score = 0
        direction = None
        vol_pump = last['volume'] > df['volume'].median() * 2

        if last['ma_fast'] > last['ma_slow'] and prev['ma_fast'] <= prev['ma_slow']: score += 1
        if last['rsi'] < 35: score += 1
        if vol_pump: score += 1
        if bids_vol > asks_vol * 1.4: score += 1
        if score >= 2 and last['rsi'] < 50: direction = "LONG"

        if last['ma_fast'] < last['ma_slow'] and prev['ma_fast'] >= prev['ma_slow']: score += 1
        if last['rsi'] > 65: score += 1
        if vol_pump: score += 1
        if asks_vol > bids_vol * 1.4: score += 1
        if score >= 2 and last['rsi'] > 50: direction = "SHORT"

        if direction:
            accuracy = 70 + int((score / 4) * 25)
            send_alert(symbol, direction, accuracy, last['close'], last['rsi'])
    except:
        pass

def send_alert(symbol, direction, accuracy, price, rsi):
    emoji = "🟢" if direction == "LONG" else "🔴"
    msg = f"{emoji} **СИГНАЛ: {symbol}**\n Направление: **{direction}**\n Надежность: **{accuracy}%**\n Цена: {price}\n RSI: {rsi:.1f}"
    try: requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    except: pass

def run_screener():
    while True:
        symbols = get_bybit_symbols()
        for symbol in symbols:
            analyze_coin(symbol)
            time.sleep(0.2)
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=run_screener, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
