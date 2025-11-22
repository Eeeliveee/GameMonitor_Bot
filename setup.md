# Установка и настройка

## 1. Получение токенов
### Telegram Bot
1. Найди @BotFather в Telegram
2. Выполни `/newbot`
3. Сохрани полученный токен

### ЮKassa
1. Зарегистрируйся на [kassa.yandex.ru](https://kassa.yandex.ru)
2. Получи shopId и secretKey
3. Настрой уведомления на ваш webhook URL

## 2. Настройка окружения
Скопируй `.env.example` в `.env` и заполни:
```bash
cp .env.example .env
nano .env