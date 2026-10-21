# Моя погода ECMWF

Приватный Telegram-бот @ObHavo_ECMWF_bot и Mini App с прогнозом, сравнением городов и картой погоды.

## Railway

- Сервис: `ob-havo-bot`, среда `production`.
- Dockerfile: `telegram/Dockerfile` (корень репозитория не менять).
- Проверка готовности: `/healthz`, порт `3000`.
- Адрес Mini App: https://ob-havo-bot-production.up.railway.app
- Секрет `TELEGRAM_BOT_TOKEN` хранится только в переменных Railway.
- `ALLOWED_TELEGRAM_USER_IDS`: личный числовой Telegram ID владельца. Пустой список закрывает доступ для всех.
- `PUBLIC_APP_URL`: `https://ob-havo-bot-production.up.railway.app`.

## Первый вход владельца

После успешного запуска откройте в боте кнопку меню «Карта погоды». Если список доступа пуст, приложение покажет ваш Telegram ID. Укажите его в `ALLOWED_TELEGRAM_USER_IDS` и перезапустите сервис. Только разрешённые ID получают прогноз и карту; группы не обслуживаются.

## Данные и возможности

Прогноз по модели ECMWF IFS через Open-Meteo; официальные ансамблевые метеограммы ECMWF Open Charts доступны отдельной кнопкой. Карта использует глобальные прогнозные поля ECMWF, анимацию времени, города и границы. Температура, осадки, влажность, ветер, облачность и давление доступны в точке. Облачность на карте — модельный прогноз, а не спутниковое изображение.

## Проверки

Node.js 24; зависимости фиксируются `pnpm-lock.yaml`.

```sh
pnpm install --frozen-lockfile
node --test tests/*.test.*
node scripts/build-telegram.mjs
node tests/check-map-worker.mjs telegram-dist
```

Не публикуйте токен в Git, логах или скриншотах. Приложение проверяет подпись Telegram и разрешённый ID на сервере; приватность репозитория не заменяет проверку доступа.
