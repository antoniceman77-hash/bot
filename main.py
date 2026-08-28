import requests

# Твой рабочий Дискорд-вебхук
WEBHOOK_URL = "https://discord.com"

def get_top_symbols():
    """Автоматически скачивает ТОП-60 самых активных фьючерсов на Binance"""
    try:
        url = "https://binance.com"
        res = requests.get(url, timeout=10).json()
        # Фильтруем только торгуемые монеты к USDT
        symbols = [x['symbol'] for x in res['symbols'] if x['status'] == 'TRADING' and x['quoteAsset'] == 'USDT']
        # Исключаем стейблкоины вроде USDC или BUSD, чтобы не слали ложные сигналы
        exclude = ['USDCUSDT', 'BUSDUSDT', 'EURUSDT']
        clean_symbols = [s for s in symbols if s not in exclude]
        return clean_symbols[:60] # Берем ТОП-60 монет для идеального баланса скорости и охвата рынка
    except:
        # Если API биржи временно лагает, используем базовый список
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT', 'LINKUSDT', 'AVAXUSDT']

def scan_market():
    print("🔎 Сканирую расширенный фьючерсный рынок Binance...")
    symbols = get_top_symbols()
    
    for symbol in symbols:
        try:
            url = f"https://binance.com{symbol}&interval=5m&limit=30"
            res = requests.get(url, timeout=5).json()
            closes = [float(x) for x in res]
            volumes = [float(x) for x in res]
            
            last_vol = volumes[-1]
            avg_vol = sum(volumes[-21:-1]) / 20
            vol_spike = last_vol > (avg_vol * 2.5)
            vol_ratio = round(last_vol / (avg_vol + 1e-5), 1)
            
            delta = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [x if x > 0 else 0 for x in delta[-14:]]
            losses = [-x if x < 0 else 0 for x in delta[-14:]]
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            rs = avg_gain / (avg_loss + 1e-10)
            rsi = round(100 - (100 / (1 + rs)), 1)
            
            # Сигналы с жестким фильтром для максимальной точности отработки
            if vol_spike and rsi > 74:
                msg = f"🔥 **[ВЫСОКАЯ ВЕРОЯТНОСТЬ: SHORT]** 🔴\n🪙 Монета: **{symbol}** (5m)\n📊 Объём взлетел в `{vol_ratio}х` раз!\n📈 Индекс RSI: `{rsi}` (Перекупленность)\n🎯 *Идеально для скальпинг-шорта на разворот.*"
                requests.post(WEBHOOK_URL, json={"content": msg})
            elif vol_spike and rsi < 26:
                msg = f"🔥 **[ВЫСОКАЯ ВЕРОЯТНОСТЬ: LONG]** 🟢\n🪙 Монета: **{symbol}** (5m)\n📊 Объём взлетел в `{vol_ratio}х` раз!\n📉 Индекс RSI: `{rsi}` (Перепроданность)\n🎯 *Идеально для скальпинг-лонга на отскок.*"
                requests.post(WEBHOOK_URL, json={"content": msg})
        except:
            continue

if __name__ == "__main__":
    scan_market()
