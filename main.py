import requests
import pandas as pd
import numpy as np
import time
import telebot
from datetime import datetime

# ========================================================
# НАСТРОЙКИ — ВСТАВЬТЕ СВОИ ДАННЫЕ СЮДА:
TELEGRAM_TOKEN = "8733364917:AAFWU8cdGkilBJGxtVlyFpb79_yuNyp35IQ"
CHAT_ID = "7220147565"
# ========================================================

BINANCE_API_URL = "https://fapi1.binance.com"
MIN_PROBABILITY = 75       # Повысили планку жесткости фильтра
PUMP_DUMP_THRESHOLD = 3.0  # Увеличили порог пампа до 3%, чтобы отсечь мелкий шум
SCAN_INTERVAL = 10         
TIMEFRAME = "5m"           

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def get_all_active_futures_once():
    url = f"{BINANCE_API_URL}/fapi/v1/exchangeInfo"
    attempts = 3
    for i in range(attempts):
        print(f"⏳ Загрузка списка всех монет с Binance (Попытка {i+1}/{attempts})...")
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                symbols = []
                for market in data['symbols']:
                    if market['status'] == 'TRADING' and market['symbol'].endswith('USDT'):
                        symbol = market['symbol']
                        if "INDEX" not in symbol and "DEFI" not in symbol and "BTCDOM" not in symbol:
                            symbols.append(symbol)
                print(f"✅ Успешно загружено {len(symbols)} монет в кэш бота!")
                return symbols
        except:
            pass
        time.sleep(3)
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

def get_klines(symbol, interval=TIMEFRAME, limit=210):
    # Запрашиваем больше свечей (210), чтобы корректно рассчитать тяжелую EMA 200
    url = f"{BINANCE_API_URL}/fapi/v1/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code != 200: return None
        return pd.DataFrame(response.json(), columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'count', 'taker_buy_volume',
            'taker_buy_quote_volume', 'ignore'
        ]).astype(float)
    except: return None

def get_order_book(symbol, limit=20):
    url = f"{BINANCE_API_URL}/fapi/v1/depth"
    params = {'symbol': symbol, 'limit': limit}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code != 200: return None
        return response.json()
    except: return None

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return (100 - (100 / (1 + rs))).iloc[-1]

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(window=period).mean().iloc[-1]

def calculate_ema200(df):
    """Вычисляет EMA 200 для определения глобального направления тренда"""
    try:
        ema = df['close'].ewm(span=200, adjust=False).mean()
        return ema.iloc[-1]
    except:
        return None

def analyze_order_book(order_book, df):
    if not order_book or df is None or 'bids' not in order_book: 
        return "⚪ Крупных заявок нет"
    try:
        bids = np.array(order_book['bids'], dtype=float)
        asks = np.array(order_book['asks'], dtype=float)
        if len(bids) == 0 or len(asks) == 0: return "⚪ Крупных заявок нет"
        
        total_bid_vol = bids[:, 1].sum()
        total_ask_vol = asks[:, 1].sum()
        
        # Повысили коэффициент стакана до 3.0 (перекос должен быть критическим)
        if total_bid_vol > total_ask_vol * 3.0: 
            return "🟢 Стенка ПОКУПАТЕЛЯ (Поддержка снизу)"
        elif total_ask_vol > total_bid_vol * 3.0: 
            return "🔴 Стенка ПРОДАВЦА (Давление сверху)"
        return "⚪ Крупных заявок нет"
    except: 
        return "⚪ Крупных заявок нет"

def format_float(val):
    if val >= 100: return f"{val:.2f}"
    if val >= 1: return f"{val:.4f}"
    return f"{val:.6f}"

def send_telegram_signal(symbol, direction, prob, price, rsi, dominance, atr, volume, is_pump_dump=False):
    # Тейк теперь рассчитывается более консервативно (1:1.5 к риску), чтобы чаще закрываться в плюс
    if "ЛОНГ" in direction or "ПАМП" in direction:
        stop_loss = price - (atr * 1.5)
        take_profit = price + (atr * 2.2) 
    else:
        stop_loss = price + (atr * 1.5)
        take_profit = price - (atr * 2.2)

    clean_name = symbol.replace('USDT', '')
    header = f"⚡ *{direction}* ⚡" if is_pump_dump else f"🚨 *СИГНАЛ: {direction}* 🚨"
    prob_text = "`Импульс тренда` 🏃‍♂️" if is_pump_dump else f"`{prob}%` 🔥"

    text = (
        f"{header}\n\n"
        f"🪙 *Монета:* #{clean_name}\n"
        f"📊 *Вероятность успеха:* {prob_text}\n"
        f"💵 *Вход по рынку:* `{format_float(price)}` USDT\n\n"
        f"🎯 *ТЕЙК (Прибыль):* `{format_float(take_profit)}` USDT\n"
        f"🛡 *СТОП (Убыток):* `{format_float(stop_loss)}` USDT\n"
        f"------------------------------------\n"
        f"📈 *RSI:* `{round(rsi, 1)}` | *Стакан:* {dominance}\n"
        f"💰 *Оборот 24ч:* `${volume/1_000_000:.1f} млн`"
    )
    try:
        bot.send_message(CHAT_ID, text, parse_mode="Markdown")
        print(f"✅ Сигнал по {symbol} отправлен в Telegram!")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

def main():
    print("🤖 Бот запущен в режиме жесткой трендовой фильтрации EMA 200...")
    global_symbols = get_all_active_futures_once()
    
    try:
        bot.send_message(CHAT_ID, f"🚀 Скринер запущен с фильтром тренда EMA 200. Ложные контр-трендовые сигналы полностью заблокированы!")
    except: return

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Сканирую {len(global_symbols)} монет из кэша...")
        
        for symbol in global_symbols:
            df = get_klines(symbol)
            if df is None or len(df) < 202 or df['close'].iloc[-1] == 0: continue
            
            volume_24h_usdt = df['quote_volume'].tail(24).sum()
            if volume_24h_usdt < 5_000_000: continue # Подняли планку ликвидности монеты до $5 млн
            
            current_price = df['close'].iloc[-1]
            ema200 = calculate_ema200(df)
            if ema200 is None: continue
            
            # Определение тренда
            is_uptrend = current_price > ema200
            is_downtrend = current_price < ema200
            
            # Проверка изменения цены за текущую 5-минутку (Памп/Дамп)
            open_price = df['open'].iloc[-1]
            price_change_pct = ((current_price - open_price) / open_price) * 100
            
            is_pump = price_change_pct >= PUMP_DUMP_THRESHOLD
            is_dump = price_change_pct <= -PUMP_DUMP_THRESHOLD
            
            # Если идет Памп, но тренд НИСХОДЯЩИЙ (цена под EMA) — блокируем лонг
            if is_pump and not is_uptrend: is_pump = False
            # If идет Дамп, но тренд ВОСХОДЯЩИЙ (цена над EMA) — блокируем шорт
            if is_dump and not is_downtrend: is_dump = False
            
            if is_pump or is_dump:
                order_book = get_order_book(symbol)
                if order_book is None: continue
                rsi = calculate_rsi(df)
                dominance = analyze_order_book(order_book, df)
                atr = calculate_atr(df)
                
                direction = f"ПАМП (+{price_change_pct:.1f}%)" if is_pump else f"ДАМП ({price_change_pct:.1f}%)"
                send_telegram_signal(symbol, direction, 85, current_price, rsi, dominance, atr, volume_24h_usdt, is_pump_dump=True)
                time.sleep(1)
                continue 
            
            # Анализ базовой стратегии
            rsi = calculate_rsi(df)
            
            # ЖЕСТКИЙ ФИЛЬТР ТРЕНДА: Пропускаем расчет, если индикаторы зовут против глобального движения
            if rsi < 28 and not is_uptrend: continue # Не покупаем на падающем рынке
            if rsi > 72 and not is_downtrend: continue # Не шортим на летящем вверх рынке
            
            order_book = get_order_book(symbol)
            if order_book is None: continue
            dominance = analyze_order_book(order_book, df)
            
            prob = 50
            if rsi < 28: prob += 20
            elif rsi > 72: prob += 20
            if "🟢" in dominance and rsi < 35: prob += 20
            elif "🔴" in dominance and rsi > 65: prob += 20
            
            if prob >= MIN_PROBABILITY:
                atr = calculate_atr(df)
                direction = "ЛОНГ (Покупка)" if rsi < 50 else "ШОРТ (Продажа)"
                send_telegram_signal(symbol, direction, prob, current_price, rsi, dominance, atr, volume_24h_usdt, is_pump_dump=False)
                time.sleep(1)
                
            time.sleep(0.15)
            
        print(f"⏱ Круг завершен. Сон {SCAN_INTERVAL} секунд...")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
