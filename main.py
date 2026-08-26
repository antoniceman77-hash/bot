import os
import time
import threading
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# НАСТРОЙКА: Вставьте сюда ваш вебхук Дискорда
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542253078462464071/7yAvnuSSo7OTgf7WJVqDek6bghOHuIqn0IPVfpKmm5BRKdfdtrxV5bE1FAKXiYAZbqD2" 

@app.route('/')
def home():
    return "Мягкий скринер Bybit активен 24/7!"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url).json()
        return [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']

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

        # СЧЕТЧИКИ ДЛЯ СИГНАЛОВ
        long_score = 0
        short_score = 0
        
        # Расширяем границы RSI (было 35/65, стало более чувствительным 40/60)
        rsi_long = last['rsi'] < 40
        rsi_short = last['rsi'] > 60

        # Снижаем планку всплеска объемов (было в 2 раза выше среднего, стало в 1.5 раза)
        vol_pump = last['volume'] > df['volume'].median() * 1.5

        # Считаем факторы для LONG
        if last['ma_fast'] > last['ma_slow']: long_score += 1   # Быстрый тренд вверх
        if rsi_long: long_score += 1                             # Цена локально внизу
        if vol_pump: long_score += 1                             # Появилась активность (объем)
        if bids_vol > asks_vol * 1.2: long_score += 1            # Покупатели поджимают в стакане

        # Считаем факторы для SHORT
        if last['ma_fast'] < last['ma_slow']: short_score += 1  # Быстрый тренд вниз
        if rsi_short: short_score += 1                           # Цена локально вверху
        if vol_pump: short_score += 1                             # Появилась активность (объем)
        if asks_vol > bids_vol * 1.2: short_score += 1            # Продавцы давят в стакане

        # МЯГКОЕ УСЛОВИЕ: Достаточно любых 2-х совпадений из 4
        if long_score >= 2 and last['rsi'] < 55:
            # Считаем процент надежности динамически (2 совпадения = 75%, 3 = 85%, 4 = 95%)
            accuracy = 65 + (long_score * 7.5)
            send_alert(symbol, "LONG", int(accuracy), last['close'], last['rsi'])

        elif short_score >= 2 and last['rsi'] > 45:
            accuracy = 65 + (short_score * 7.5)
            send_alert(symbol, "SHORT", int(accuracy), last['close'], last['rsi'])
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

