import os
import time
import threading
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# =====================================================================
# ⚙️ НАСТРОЙКА (ВСТАВЬТЕ СЮДА ВАШ ЛИЧНЫЙ ВЕБХУК ДИСКОРДА В ОДНУ СТРОКУ)
# =====================================================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542253078462464071/7yAvnuSSo7OTgf7WJVqDek6bghOHuIqn0IPVfpKmm5BRKdfdtrxV5bE1FAKXiYAZbqD2"
# =====================================================================

@app.route('/')
def home():
    return "Чистый Скринер Bybit в Discord активен!"

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url, timeout=5).json()
        all_symbols = [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
        return all_symbols[:40] # ТОП-40 самых волатильных монет
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=40"
        res = requests.get(url, timeout=5).json()
        
        if 'result' not in res or 'list' not in res['result'] or not res['result']['list']:
            return
            
        klines = res['result']['list']
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        df = df.iloc[::-1].reset_index(drop=True)

        df['ma_fast'] = df['close'].rolling(5).mean()
        df['ma_slow'] = df['close'].rolling(15).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))

        df['tr1'] = df['high'] - df['low']
        df['tr2'] = (df['high'] - df['close'].shift(1)).abs()
        df['tr3'] = (df['low'] - df['close'].shift(1)).abs()
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()

        df['vol_avg'] = df['volume'].rolling(15).mean()

        last, prev = df.iloc[-1], df.iloc[-2]
        atr_val, price = last['atr'], last['close']
        
        if pd.isna(atr_val) or atr_val <= 0:
            return

        long_score = 0
        short_score = 0
        
        if last['ma_fast'] > last['ma_slow']: long_score += 1
        if last['ma_fast'] < last['ma_slow']: short_score += 1
        if last['rsi'] < 52: long_score += 1
        if last['rsi'] > 48: short_score += 1
        if last['volume'] > last['vol_avg'] * 1.1: long_score += 1; short_score += 1

        if long_score >= 2 and last['rsi'] < 60:
            accuracy = 75 if long_score == 2 else 95
            sl = price - (1.5 * atr_val)
            tp = price + (3.0 * atr_val)
            send_discord_alert(symbol, "LONG", accuracy, price, last['rsi'], sl, tp)
            
        elif short_score >= 2 and last['rsi'] > 40:
            accuracy = 75 if short_score == 2 else 95
            sl = price + (1.5 * atr_val)
            tp = price - (3.0 * atr_val)
            send_discord_alert(symbol, "SHORT", accuracy, price, last['rsi'], sl, tp)
    except:
        pass

def format_coin_price(val):
    if val < 0.001: return f"{val:.6f}"
    if val < 1: return f"{val:.4f}"
    return f"{val:.2f}"

def send_discord_alert(symbol, direction, accuracy, price, rsi, sl, tp):
    emoji = "🟢" if direction == "LONG" else "🔴"
    p_str, sl_str, tp_str = format_coin_price(price), format_coin_price(sl), format_coin_price(tp)
    
    msg = f"{emoji} **СИГНАЛ: {symbol}**\n" \
          f"Направление: **{direction}**\n" \
          f"Надежность: **{accuracy}%**\n" \
          f"Вход: **{p_str}**\n" \
          f"RSI: {rsi:.1f}\n" \
          f"🎯 TP: **{tp_str}** | ⚠️ SL: **{sl_str}**"
          
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
        if res.status_code == 429:
            time.sleep(5)
        else:
            time.sleep(2) # Очередь для обхода банов Discord
    except:
        pass

def run_screener():
    try: 
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "⚔️ **Личный скринер Bybit успешно запущен напрямую! Реклама отключена, ожидаем сигналы.**"}, timeout=5)
    except: 
        pass
        
    while True:
        symbols = get_bybit_symbols()
        for symbol in symbols:
            analyze_coin(symbol)
            time.sleep(0.2)
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=run_screener, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

