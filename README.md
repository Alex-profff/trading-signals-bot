# Trading Signals Bot

A Telegram bot for crypto trading signals with portfolio tracking.

## Features
- LONG/SHORT signals based on RSI + MA20 + MA50
- Hourly monitoring of BTC, ETH, SOL, BNB, ADA
- 24h ASCII price chart
- Real-time portfolio tracker with PnL

## Commands
- `/price` — current prices and RSI
- `/signal` — check signals now
- `/chart BTC` — price chart
- `/add BTC 0.5` — add a holding to the portfolio
- `/portfolio` — holdings and PnL
- `/status` — bot status

## Stack
Python · python-telegram-bot · Binance API · pandas

## Run
1. Create a `.env` file with `BOT_TOKEN` and `CHAT_ID`
2. `pip install -r requirements.txt`
3. `python bot.py`
