import os
import time
import threading
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# НАСТРОЙКА: Вставьте ваш вебхук Дискорда внутрь кавычек в одну строку
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542253078462464071/7yAvnuSSo7OTgf7WJVqDek6bghOHuIqn0IPVfpKmm5BRKdfdtrxV5bE1FAKXiYAZbqD2" 

@app.route('/')
def home():
    return "Скринер Bybit с защитой от спама активен!"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url).json()
        return [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=30"
        res = requests.get(url).json()
        
        if 'result' not in res or 'list' not in res['result'] or not res['result']['list']:
            return
            
        klines = res['result']['list']
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        # Индикаторы скальпинга
        df['ma_fast'] = df['close'].rolling(5).mean()
        df['ma_slow'] = df['close'].rolling(15).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        long_score = 0
        short_score = 0
        
        # Анализ условий
        if last['ma_fast'] > last['ma_slow']: long_score += 1
        if last['ma_fast'] < last['ma_slow']: short_score += 1
        
        if last['rsi'] < 45: long_score += 1
        if last['rsi'] > 55: short_score += 1
        
        if last['volume'] > prev['volume']:
            long_score += 1
            short_score += 1

        # Отправка с динамической надежностью
        if long_score >= 2 and last['rsi'] < 60:
            accuracy = 75 if long_score == 2 else 95
            send_alert(symbol, "LONG", accuracy, last['close'], last['rsi'])
            
        elif short_score >= 2 and last['rsi'] > 40:
            accuracy = 75 if short_score == 2 else 95
            send_alert(symbol, "SHORT", accuracy, last['close'], last['rsi'])
            
    except:
        pass

def send_alert(symbol, direction, accuracy, price, rsi):
    emoji = "🟢" if direction == "LONG" else "🔴"
    # Форматируем цену, чтобы убрать лишние нули для дешевых монет
    formatted_price = f"{price:.4f}".rstrip('0').rstrip('.') if price < 1 else f"{price:.2f}"
    
    msg = f"{emoji} **СИГНАЛ: {symbol}**\n" \
          f" Направление: **{direction}**\n" \
          f" Надежность: **{accuracy}%**\n" \
          f" Цена входа: **{formatted_price}**\n" \
          f" RSI: {rsi:.1f}"
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
        # Если Discord говорит, что мы шлем слишком часто, делаем паузу
        if res.status_code == 429:
            time.sleep(5)
        else:
            time.sleep(2) # Обязательная пауза 2 секунды между сигналами для защиты от блокировок
    except:
        pass

def run_screener():
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "🔄 **Скринер Bybit успешно перезапущен. Защита от спама активна!**"}, timeout=5)
    except:
        pass
        
    while True:
        symbols = get_bybit_symbols()
        for symbol in symbols:
            analyze_coin(symbol)
            time.sleep(0.2) # Не перегружаем API биржи
        time.sleep(60) # Спокойно ждем 1 минуту перед новым кругом проверки

if __name__ == "__main__":
    threading.Thread(target=run_screener, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
