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
```

## 3. Запуск через Docker (рекомендуется)
```bash
docker-compose up -d
```

## 4. Запуск вручную
```bash
pip install -r requirements.txt
python main.py
```

## 5.Первая настройка
1. Найди бота в Telegram

2. Начни с команды /start

3. Настрой админов через переменную ADMIN_IDS

```text

**3. .env.example:**
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here

# ЮKassa Payments
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Администраторы (через запятую)
ADMIN_IDS=123456789,987654321

# Настройки бота
DEBUG=False
LOG_LEVEL=INFO

# База данных
DB_PATH=/data/bot.db

# Webhook настройки (для продакшена)
WEBHOOK_HOST=https://yourdomain.com
WEBHOOK_SECRET=your_webhook_secret
```