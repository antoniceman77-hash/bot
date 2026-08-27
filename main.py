import os
import time
import requests
import pandas as pd

# =====================================================================
# ⚙️ НАСТРОЙКИ (ВСТАВЬТЕ ВАШИ ДАННЫЕ ВНУТРИ КАВЫЧЕК В ОДНУ СТРОКУ)
# =====================================================================
TELEGRAM_USER_ID = "7143940100"
BOT_TOKEN = "8845220550:AAHhBRMKYFgqzqn-CTMEMVDcL5W-KOlJvlE"
# =====================================================================

def get_bybit_symbols():
    try:
        url = "https://bybit.com"
        res = requests.get(url, timeout=5).json()
        all_symbols = [s['symbol'] for s in res['result']['list'] if s['status'] == 'Trading' and s['quoteCoin'] == 'USDT']
        return all_symbols[:40]
    except:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def analyze_coin(symbol):
    try:
        url = f"https://bybit.com{symbol}&interval=5&limit=30"
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
        gain = (delta.where(delta > 0, 0)).rolling(10).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(10).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))

        df['tr1'] = df['high'] - df['low']
        df['tr2'] = (df['high'] - df['close'].shift(1)).abs()
        df['tr3'] = (df['low'] - df['close'].shift(1)).abs()
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(10).mean()

        df['vol_avg'] = df['volume'].rolling(10).mean()

        last, prev = df.iloc[-1], df.iloc[-2]
        atr_val, price = last['atr'], last['close']
        
        if pd.isna(atr_val) or atr_val <= 0:
            return

        long_score, short_score = 0, 0
        if last['ma_fast'] > last['ma_slow']: long_score += 1
        if last['ma_fast'] < last['ma_slow']: short_score += 1
        if last['rsi'] < 52: long_score += 1
        if last['rsi'] > 48: short_score += 1
        if last['volume'] > last['vol_avg'] * 1.1: long_score += 1; short_score += 1

        if long_score >= 2 and last['rsi'] < 60:
            accuracy = 75 if long_score == 2 else 95
            sl, tp = price - (1.5 * atr_val), price + (3.0 * atr_val)
            send_telegram_alert(symbol, "LONG", accuracy, price, last['rsi'], sl, tp)
            
        elif short_score >= 2 and last['rsi'] > 40:
            accuracy = 75 if short_score == 2 else 95
            sl, tp = price + (1.5 * atr_val), price - (3.0 * atr_val)
            send_telegram_alert(symbol, "SHORT", accuracy, price, last['rsi'], sl, tp)
    except:
        pass

def format_coin_price(val):
    if val < 0.001: return f"{val:.6f}"
    if val < 1: return f"{val:.4f}"
    return f"{val:.2f}"

def send_telegram_alert(symbol, direction, accuracy, price, rsi, sl, tp):
    emoji = "🟢" if direction == "LONG" else "🔴"
    p_str, sl_str, tp_str = format_coin_price(price), format_coin_price(sl), format_coin_price(tp)
    
    msg = f"{emoji} **СИГНАЛ: {symbol}**\n" \
          f"Направление: **{direction}**\n" \
          f"Надежность: **{accuracy}%**\n" \
          f"Вход: **{p_str}**\n" \
          f"RSI: {rsi:.1f}\n" \
          f"🎯 TP: **{tp_str}** | ⚠️ SL: **{sl_str}**"
          
    url = f"https://telegram.org{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
        time.sleep(2)
    except:
        pass

if __name__ == "__main__":
    url = f"https://telegram.org{BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_USER_ID, "text": "🚀 **Скринер v7.2 успешно запущен на мощном сервере! Ждем сигналы.**", "parse_mode": "Markdown"}, timeout=5)
    except: pass
        
    while True:
        symbols = get_bybit_symbols()
        for symbol in symbols:
            analyze_coin(symbol)
            time.sleep(0.3)
        time.sleep(20)
