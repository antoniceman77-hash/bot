import os
import time
import threading
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# =====================================================================
# ⚙️ НАСТРОЙКА (ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ИЗ PUSHBULLET ВНУТРЬ КАВЫЧЕК)
# =====================================================================
PUSHBULLET_TOKEN = "o.2R13tnpoUOLR3xk69oN4KJOsF9WMDars"
# =====================================================================

@app.route('/')
def home():
    return "Скринер Bybit через Pushbullet активен!"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url).json()
        return [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT'][:30]
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=30"
        res = requests.get(url).json()
        klines = res['result']['list']
        
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        df['ma_fast'] = df['close'].rolling(5).mean()
        df['ma_slow'] = df['close'].rolling(15).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(10).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(10).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))

        last, prev = df.iloc[-1], df.iloc[-2]
        price = last['close']

        # Мягкий скальпинг: пересечение средних + фильтр RSI
        if last['ma_fast'] > last['ma_slow'] and prev['ma_fast'] <= prev['ma_slow']:
            if last['rsi'] < 60:
                send_push(f"🟢 LONG: {symbol}", f"Цена: {price} | RSI: {last['rsi']:.1f}")
                
        elif last['ma_fast'] < last['ma_slow'] and prev['ma_fast'] >= prev['ma_slow']:
            if last['rsi'] > 40:
                send_push(f"🔴 SHORT: {symbol}", f"Цена: {price} | RSI: {last['rsi']:.1f}")
    except:
        pass

def send_push(title, body):
    url = "https://pushbullet.com"
    headers = {"Access-Token": PUSHBULLET_TOKEN, "Content-Type": "application/json"}
    payload = {"type": "note", "title": title, "body": body}
    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
        time.sleep(3) # Защита от спама
    except:
        pass

def run_screener():
    # Проверочный моментальный пуш при старте
    send_push("🚀 Скринер Bybit", "Бот успешно запущен и начал сканирование!")
    while True:
        symbols = get_bybit_symbols()
        for symbol in symbols:
            analyze_coin(symbol)
            time.sleep(0.2)
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_screener, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
