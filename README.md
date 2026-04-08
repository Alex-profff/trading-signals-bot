# Trading Signals Bot

Telegram бот для торговых сигналов по криптовалюте с трекером портфеля.

## Функции
- Сигналы LONG/SHORT на основе RSI + MA20 + MA50
- Мониторинг BTC, ETH, SOL, BNB, ADA каждый час
- ASCII график цены за 24ч
- Трекер портфеля с PnL в реальном времени

## Команды
- /price — текущие цены и RSI
- /signal — проверить сигналы сейчас
- /chart BTC — график цены
- /add BTC 0.5 — добавить в портфель
- /portfolio — портфель и PnL
- /status — статус бота

## Стек
Python, python-telegram-bot, Binance API, pandas

## Запуск
1. Создай .env файл с BOT_TOKEN и CHAT_ID
2. pip install -r requirements.txt
3. python bot.py
