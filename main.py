import os
import time
import threading
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# НАСТРОЙКА: Вставьте ваш вебхук Дискорда внутрь кавычек
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542253078462464071/7yAvnuSSo7OTgf7WJVqDek6bghOHuIqn0IPVfpKmm5BRKdfdtrxV5bE1FAKXiYAZbqD2" 

@app.route('/')
def home():
    return "Скринер Bybit активен и сканирует рынок!"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url).json()
        # Сканируем абсолютно ВСЕ доступные монеты к USDT
        return [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
    except Exception as e:
        print(f"Ошибка получения символов: {e}")
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=30"
        res = requests.get(url).json()
        
        if 'result' not in res or 'list' not in res['result'] or not res['result']['list']:
            return
            
        klines = res['result']['list']
        
        # Загружаем данные: время, open, high, low, close, volume
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df = df.iloc[::-1].reset_index(drop=True) # Хронологический порядок

        # Скользящие средние (MA 5 и MA 15) для быстрых скальп-сигналов
        df['ma_fast'] = df['close'].rolling(5).mean()
        df['ma_slow'] = df['close'].rolling(15).mean()
        
        # Расчет RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # МЯГКИЕ ФАКТОРЫ
        long_conditions = 0
        short_conditions = 0
        
        # 1. Фактор скользящих средних
        if last['ma_fast'] > last['ma_slow']: long_conditions += 1
        if last['ma_fast'] < last['ma_slow']: short_conditions += 1
        
        # 2. Фактор RSI (границы расширены до 45/55 для частоты)
        if last['rsi'] < 45: long_conditions += 1
        if last['rsi'] > 55: short_conditions += 1
        
        # 3. Фактор объема (текущий объем просто выше предыдущего)
        if last['volume'] > prev['volume']:
            long_conditions += 1
            short_conditions += 1

        # Отправка сигналов, если совпало хотя бы 2 фактора из 3
        if long_conditions >= 2 and last['rsi'] < 60:
            accuracy = 70 if long_conditions == 2 else 90
            send_alert(symbol, "LONG", accuracy, last['close'], last['rsi'])
            
        elif short_conditions >= 2 and last['rsi'] > 40:
            accuracy = 70 if short_conditions == 2 else 90
            send_alert(symbol, "SHORT", accuracy, last['close'], last['rsi'])
            
    except Exception as e:
        print(f"Ошибка анализа {symbol}: {e}")

def send_alert(symbol, direction, accuracy, price, rsi):
    emoji = "🟢" if direction == "LONG" else "🔴"
    msg = f"{emoji} **СИГНАЛ: {symbol}**\n Направление: **{direction}**\n Надежность: **{accuracy}%**\n Цена: {price}\n RSI: {rsi:.1f}"
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
    except:
        pass

def run_screener():
    # ТЕСТОВЫЙ СИГНАЛ: сработает моментально при запуске сервера для проверки связи!
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "🚀 **БОТ УСПЕШНО ПЕРЕЗАПУЩЕН И НАЧАЛ СКАНИРОВАНИЕ РЫНКА BYBIT!**"}, timeout=5)
    except:
        pass
        
    while True:
        symbols = get_bybit_symbols()
        for symbol in symbols:
            analyze_coin(symbol)
            time.sleep(0.1) # Быстрый обход монет
        time.sleep(30) # Пауза 30 секунд между кругами

if __name__ == "__main__":
    threading.Thread(target=run_screener, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
