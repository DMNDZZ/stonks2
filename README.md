# Stonks2

## Запуск локально

Установите [uv](https://docs.astral.sh/uv/) и заполните `.env` по образцу. Поля Google service account указываются отдельно; в `GOOGLE_PRIVATE_KEY` переводы строк задаются как `\n`.

```sh
uv sync --locked
uv run python bot.py
```

## Запуск через Docker Compose

Заполните `.env`, затем выполните:

```sh
docker compose up --build -d
docker compose logs -f bot
```

Для прокси Telegram укажите `BOT_PROXY_URL` в `.env` (например, `socks5://proxy-host:1080` или `http://proxy-host:3128`). Прокси используется и для запросов бота, и для long polling. Адрес должен быть доступен из контейнера.

Compose сохраняет сгенерированные договоры и акты в `documents/`, а Google credentials подключает в контейнер только для чтения.
