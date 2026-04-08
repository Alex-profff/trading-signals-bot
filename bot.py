import os
import requests
import pandas as pd
import asyncio
import schedule
import time
import threading
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
last_signals = {}
portfolios = {}  # {user_id: {symbol: amount}}


def get_klines(symbol, interval="1h", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df
    except Exception as e:
        print(f"Ошибка {symbol}: {e}")
        return None


def get_price(symbol):
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        return float(r.json()["price"])
    except:
        return None


def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def analyze_symbol(symbol):
    df = get_klines(symbol)
    if df is None or len(df) < 50:
        return None
    closes = df["close"]
    current_price = closes.iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma50 = closes.rolling(50).mean().iloc[-1]
    rsi = calculate_rsi(closes).iloc[-1]
    avg_volume = df["volume"].rolling(20).mean().iloc[-1]
    current_volume = df["volume"].iloc[-1]
    volume_surge = current_volume > avg_volume * 1.5
    signal = None
    if rsi < 35 and current_price > ma20 and ma20 > ma50:
        signal = "LONG"
    elif rsi > 65 and current_price < ma20 and ma20 < ma50:
        signal = "SHORT"
    if signal:
        return {
            "symbol": symbol,
            "signal": signal,
            "price": current_price,
            "rsi": round(rsi, 1),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "volume_surge": volume_surge
        }
    return None


def format_signal(data):
    symbol = data["symbol"].replace("USDT", "")
    emoji = "🟢" if data["signal"] == "LONG" else "🔴"
    vol = "📊 Объём повышен!\n" if data["volume_surge"] else ""
    return (
        f"{emoji} <b>{data['signal']} сигнал — {symbol}</b>\n\n"
        f"💰 Цена: <b>${data['price']:,.2f}</b>\n"
        f"📈 RSI: <b>{data['rsi']}</b>\n"
        f"📉 MA20: <b>${data['ma20']:,.2f}</b>\n"
        f"📉 MA50: <b>${data['ma50']:,.2f}</b>\n"
        f"{vol}"
        f"⚠️ Не является финансовым советом"
    )


def make_chart(symbol, prices, interval="1h"):
    """Текстовый ASCII график цены"""
    name = symbol.replace("USDT", "")
    last_24 = prices.tail(24).tolist()
    min_p = min(last_24)
    max_p = max(last_24)
    height = 8
    chart_rows = []
    for row in range(height, 0, -1):
        line = ""
        threshold = min_p + (max_p - min_p) * (row / height)
        for price in last_24:
            if price >= threshold:
                line += "█"
            else:
                line += " "
        price_label = f"${min_p + (max_p - min_p) * (row / height):,.0f}"
        chart_rows.append(f"{price_label:>12} |{line}")
    chart_rows.append(f"{'':>12} +{'─' * 24}")
    chart_rows.append(f"{'':>12}  -24ч{'':>16}сейчас")
    change = ((last_24[-1] - last_24[0]) / last_24[0]) * 100
    direction = "📈" if change > 0 else "📉"
    result = f"{direction} <b>{name} за 24ч ({interval})</b>\n\n"
    result += "<pre>" + "\n".join(chart_rows) + "</pre>\n\n"
    result += f"Открытие: <b>${last_24[0]:,.2f}</b>\n"
    result += f"Текущая:  <b>${last_24[-1]:,.2f}</b>\n"
    result += f"Изменение: <b>{change:+.2f}%</b>"
    return result


async def send_signal(bot, text):
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")


def check_signals(bot):
    print("Проверка сигналов...")
    for symbol in SYMBOLS:
        result = analyze_symbol(symbol)
        if result:
            signal_key = f"{symbol}_{result['signal']}"
            last = last_signals.get(signal_key)
            if last != round(result["price"], 0):
                text = format_signal(result)
                asyncio.run(send_signal(bot, text))
                last_signals[signal_key] = round(result["price"], 0)
                print(f"Сигнал: {symbol} {result['signal']}")
        else:
            df = get_klines(symbol)
            if df is not None:
                price = df["close"].iloc[-1]
                rsi = calculate_rsi(df["close"]).iloc[-1]
                print(f"{symbol.replace('USDT','')}: ${price:,.2f} | RSI: {rsi:.1f}")


# ===== КОМАНДЫ БОТА =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 <b>Trading Signals Bot</b>\n\n"
        "Анализирую BTC, ETH, SOL, BNB, ADA каждый час.\n"
        "Сигналы на основе RSI + скользящих средних.\n\n"
        "<b>Команды:</b>\n"
        "/price — текущие цены и RSI\n"
        "/signal — проверить сигналы сейчас\n"
        "/chart BTC — график цены за 24ч\n"
        "/portfolio — мой портфель и PnL\n"
        "/add BTC 0.5 — добавить монету в портфель\n"
        "/remove BTC — убрать монету из портфеля\n"
        "/status — статус бота",
        parse_mode="HTML"
    )


async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "💰 <b>Текущие цены:</b>\n\n"
    for symbol in SYMBOLS:
        df = get_klines(symbol)
        if df is not None:
            price = df["close"].iloc[-1]
            rsi = calculate_rsi(df["close"]).iloc[-1]
            name = symbol.replace("USDT", "")
            emoji = "🟢" if rsi < 40 else "🔴" if rsi > 60 else "⚪"
            text += f"{emoji} <b>{name}:</b> ${price:,.2f} | RSI: {rsi:.1f}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Анализирую рынок...")
    found = False
    for symbol in SYMBOLS:
        result = analyze_symbol(symbol)
        if result:
            await update.message.reply_text(format_signal(result), parse_mode="HTML")
            found = True
    if not found:
        await update.message.reply_text("⚪ Сигналов нет. Рынок в нейтральной зоне.")


async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Укажи монету: /chart BTC")
        return
    symbol = args[0].upper() + "USDT"
    if symbol not in SYMBOLS:
        await update.message.reply_text(f"Доступные монеты: {', '.join([s.replace('USDT','') for s in SYMBOLS])}")
        return
    await update.message.reply_text("📊 Строю график...")
    df = get_klines(symbol, interval="1h", limit=25)
    if df is None:
        await update.message.reply_text("Ошибка получения данных.")
        return
    text = make_chart(symbol, df["close"])
    await update.message.reply_text(text, parse_mode="HTML")


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Формат: /add BTC 0.5")
        return
    symbol = args[0].upper()
    try:
        amount = float(args[1])
    except:
        await update.message.reply_text("Неверное количество.")
        return

    user_id = update.effective_user.id
    if user_id not in portfolios:
        portfolios[user_id] = {}

    symbol_usdt = symbol + "USDT"
    price = get_price(symbol_usdt)
    if price is None:
        await update.message.reply_text(f"Монета {symbol} не найдена.")
        return

    portfolios[user_id][symbol] = {
        "amount": amount,
        "buy_price": price
    }
    await update.message.reply_text(
        f"✅ Добавлено: <b>{amount} {symbol}</b>\n"
        f"Цена входа: <b>${price:,.2f}</b>",
        parse_mode="HTML"
    )


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Формат: /remove BTC")
        return
    symbol = args[0].upper()
    user_id = update.effective_user.id
    if user_id in portfolios and symbol in portfolios[user_id]:
        del portfolios[user_id][symbol]
        await update.message.reply_text(f"✅ {symbol} удалён из портфеля.")
    else:
        await update.message.reply_text(f"❌ {symbol} не найден в портфеле.")


async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in portfolios or not portfolios[user_id]:
        await update.message.reply_text(
            "Портфель пуст.\n"
            "Добавь монету: /add BTC 0.5"
        )
        return

    text = "💼 <b>Мой портфель:</b>\n\n"
    total_value = 0
    total_invested = 0

    for symbol, data in portfolios[user_id].items():
        current_price = get_price(symbol + "USDT")
        if current_price is None:
            continue
        amount = data["amount"]
        buy_price = data["buy_price"]
        current_value = amount * current_price
        invested = amount * buy_price
        pnl = current_value - invested
        pnl_pct = ((current_price - buy_price) / buy_price) * 100
        emoji = "📈" if pnl > 0 else "📉"
        text += (
            f"{emoji} <b>{symbol}</b>: {amount}\n"
            f"   Вход: ${buy_price:,.2f} → Сейчас: ${current_price:,.2f}\n"
            f"   PnL: <b>${pnl:+,.2f} ({pnl_pct:+.2f}%)</b>\n\n"
        )
        total_value += current_value
        total_invested += invested

    total_pnl = total_value - total_invested
    total_pnl_pct = ((total_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0
    emoji = "📈" if total_pnl > 0 else "📉"
    text += f"{'─'*25}\n"
    text += f"{emoji} <b>Итого:</b> ${total_value:,.2f}\n"
    text += f"<b>PnL: ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)</b>"

    await update.message.reply_text(text, parse_mode="HTML")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ <b>Бот работает</b>\n\n"
        f"Отслеживаю: {', '.join([s.replace('USDT','') for s in SYMBOLS])}\n"
        f"Интервал: 1 час\n"
        f"Индикаторы: RSI + MA20 + MA50",
        parse_mode="HTML"
    )


def run_scheduler(bot):
    schedule.every(1).hours.do(check_signals, bot=bot)
    check_signals(bot)
    while True:
        schedule.run_pending()
        time.sleep(1)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("portfolio", portfolio_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    bot = Bot(token=BOT_TOKEN)
    t = threading.Thread(target=run_scheduler, args=(bot,), daemon=True)
    t.start()

    print("Trading Signals Bot запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
