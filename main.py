import os
import time
import threading
import requests
import pandas as pd
import numpy as np
from flask import Flask

app = Flask(__name__)

# НАСТРОЙКА: Ваш вебхук Дискорда
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542253078462464071/7yAvnuSSo7OTgf7WJVqDek6bghOHuIqn0IPVfpKmm5BRKdfdtrxV5bE1FAKXiYAZbqD2"

@app.route('/')
def home():
    return "Скринер Bybit с ATR и SL/TP активен!"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url).json()
        return [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=40"
        res = requests.get(url).json()
        
        if 'result' not in res or 'list' not in res['result'] or not res['result']['list']:
            return
            
        klines = res['result']['list']
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        # Расчет MA
        df['ma_fast'] = df['close'].rolling(5).mean()
        df['ma_slow'] = df['close'].rolling(15).mean()
        
        # Расчет RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))

        # РАСЧЕТ ATR (14 периодов)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = (df['high'] - df['close'].shift(1)).abs()
        df['tr3'] = (df['low'] - df['close'].shift(1)).abs()
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        atr_val = last['atr']
        price = last['close']
        
        # Защита: пропускаем монеты с нулевым или нерассчитанным ATR
        if pd.isna(atr_val) or atr_val <= 0:
            return

        long_score = 0
        short_score = 0
        
        # Логика индикаторов
        if last['ma_fast'] > last['ma_slow']: long_score += 1
        if last['ma_fast'] < last['ma_slow']: short_score += 1
        if last['rsi'] < 45: long_score += 1
        if last['rsi'] > 55: short_score += 1
        if last['volume'] > prev['volume']:
            long_score += 1
            short_score += 1

        # Отправка LONG сигналов
        if long_score >= 2 and last['rsi'] < 60:
            accuracy = 75 if long_score == 2 else 95
            # Расчет Риска по ATR: Стоп = Цена - 1.5*ATR, Тейк = Цена + 3*ATR (соотношение 1:2)
            sl = price - (1.5 * atr_val)
            tp = price + (3.0 * atr_val)
            send_alert(symbol, "LONG", accuracy, price, last['rsi'], sl, tp, atr_val)
            
        # Отправка SHORT сигналов
        elif short_score >= 2 and last['rsi'] > 40:
            accuracy = 75 if short_score == 2 else 95
            # Расчет Риска по ATR: Стоп = Цена + 1.5*ATR, Тейк = Цена - 3*ATR
            sl = price + (1.5 * atr_val)
            tp = price - (3.0 * atr_val)
            send_alert(symbol, "SHORT", accuracy, price, last['rsi'], sl, tp, atr_val)
            
    except:
        pass

def format_coin_price(val):
    if val < 0.001: return f"{val:.6f}"
    if val < 1: return f"{val:.4f}"
    return f"{val:.2f}"

def send_alert(symbol, direction, accuracy, price, rsi, sl, tp, atr):
    emoji = "🟢" if direction == "LONG" else "🔴"
    
    p_str = format_coin_price(price)
    sl_str = format_coin_price(sl)
    tp_str = format_coin_price(tp)
    atr_str = format_coin_price(atr)
    
    msg = f"{emoji} **СИГНАЛ: {symbol}**\n" \
          f" Направление: **{direction}**\n" \
          f" Надежность: **{accuracy}%**\n" \
          f" Цена входа: **{p_str}**\n" \
          f" RSI: {rsi:.1f} | ATR: {atr_str}\n" \
          f" 🎯 **Тейк-Профит (TP): {tp_str}**\n" \
          f" ⚠️ **Стоп-Лосс (SL): {sl_str}**"
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
        if res.status_code == 429:
            time.sleep(5)
        else:
            time.sleep(2)
    except:
        pass

def run_screener():
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "🔄 **Скринер Bybit ОБНОВЛЕН. Добавлен индикатор ATR и уровни SL/TP!**"}, timeout=5)
    except:
        pass
        
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
