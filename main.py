import requests

# Твой рабочий Дискорд-вебхук
WEBHOOK_URL = "https://discord.com"
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT', 'LINKUSDT', 'AVAXUSDT', 'ADAUSDT']

def scan_market():
    print("🔎 Сканирую фьючерсы Binance...")
    for symbol in SYMBOLS:
        try:
            url = f"https://binance.com{symbol}&interval=5m&limit=30"
            res = requests.get(url, timeout=10).json()
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
            
            if vol_spike and rsi > 73:
                msg = f"🚨 **[SIGNAL: SHORT]** 🔴\n🪙 Монета: **{symbol}** (5m)\n🔥 Объём взлетел в `{vol_ratio}х` раз!\n📊 RSI: `{rsi}` (Перекупленность)"
                requests.post(WEBHOOK_URL, json={"content": msg})
            elif vol_spike and rsi < 27:
                msg = f"🚨 **[SIGNAL: LONG]** 🟢\n🪙 Монета: **{symbol}** (5m)\n🔥 Объём взлетел в `{vol_ratio}х` раз!\n📊 RSI: `{rsi}` (Перепроданность)"
                requests.post(WEBHOOK_URL, json={"content": msg})
        except:
            continue

if __name__ == "__main__":
    scan_market()

