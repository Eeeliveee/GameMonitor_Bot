import logging

import aiosqlite
import os

from aiogram import Bot

from GameMonitor_Bot.main import bot, dp, setup_logging

DB_PATH = "game_monitor.db"


async def create_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица подписок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_name TEXT NOT NULL,
                target_price INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица для найденных сделок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_name TEXT NOT NULL,
                current_price REAL NOT NULL,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица для авто-покупок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS auto_buy_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_name TEXT NOT NULL,
                max_price REAL NOT NULL,
                platform TEXT DEFAULT 'steam',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица выполненных покупок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS completed_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_name TEXT NOT NULL,
                purchase_price REAL NOT NULL,
                platform TEXT NOT NULL,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_balance (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')


# ФУНКЦИИ ДЛЯ ПОДПИСОК
async def add_subscription(user_id, game_name, target_price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO subscriptions (user_id, game_name, target_price) VALUES (?, ?, ?)",
            (user_id, game_name, target_price)
        )
        await db.commit()


async def get_user_subscriptions(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT game_name, target_price FROM subscriptions WHERE user_id = ?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [{"game_name": row[0], "target_price": row[1]} for row in rows]


# ФУНКЦИИ ДЛЯ АВТО-ПОКУПОК
async def add_auto_buy_rule(user_id, game_name, max_price, platform="steam"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO auto_buy_rules (user_id, game_name, max_price, platform) VALUES (?, ?, ?, ?)",
            (user_id, game_name, max_price, platform)
        )
        await db.commit()


async def get_active_auto_buy_rules():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, game_name, max_price, platform FROM auto_buy_rules WHERE is_active = TRUE"
        )
        rows = await cursor.fetchall()

        rules = []
        for row in rows:
            rules.append({
                'id': row[0],
                'user_id': row[1],
                'game_name': row[2],
                'max_price': row[3],
                'platform': row[4]
            })
        return rules


async def get_user_auto_buy_rules(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, game_name, max_price, platform, is_active FROM auto_buy_rules WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()

        rules = []
        for row in rows:
            rules.append({
                'id': row[0],
                'user_id': row[1],
                'game_name': row[2],
                'max_price': row[3],
                'platform': row[4],
                'is_active': bool(row[5])
            })
        return rules


async def disable_auto_buy_rule(rule_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE auto_buy_rules SET is_active = FALSE WHERE id = ?",
            (rule_id,)
        )
        await db.commit()


async def log_purchase(user_id, game_name, purchase_price, platform):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO completed_purchases (user_id, game_name, purchase_price, platform) VALUES (?, ?, ?, ?)",
            (user_id, game_name, purchase_price, platform)
        )
        await db.commit()


async def get_user_balance(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT balance FROM user_balance WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_user_balance(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем есть ли запись
        cursor = await db.execute("SELECT 1 FROM user_balance WHERE user_id = ?", (user_id,))
        exists = await cursor.fetchone()

        if exists:
            await db.execute(
                "UPDATE user_balance SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
        else:
            await db.execute(
                "INSERT INTO user_balance (user_id, balance) VALUES (?, ?)",
                (user_id, amount)
            )
        await db.commit()


async def get_user_transactions(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем историю из completed_purchases
        cursor = await db.execute(
            "SELECT game_name, purchase_price, platform, purchase_date FROM completed_purchases WHERE user_id = ? ORDER BY purchase_date DESC",
            (user_id,)
        )
        purchases = await cursor.fetchall()

        transactions = []
        for purchase in purchases:
            transactions.append({
                'type': 'purchase',
                'game_name': purchase[0],
                'amount': -purchase[1],
                'platform': purchase[2],
                'date': purchase[3]
            })

        return transactions


# Функции для статистики
async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM user_balance")
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_today_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM user_balance 
            WHERE DATE(updated_at) = DATE('now')
        """)
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_total_revenue():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT SUM(purchase_price) FROM completed_purchases")
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_active_subscriptions():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM subscriptions")
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_users_statistics():
    async with aiosqlite.connect(DB_PATH) as db:
        # Всего пользователей
        cursor = await db.execute("SELECT COUNT(*) FROM user_balance")
        total = (await cursor.fetchone())[0]

        # Активных (кто пополнял баланс)
        cursor = await db.execute("SELECT COUNT(*) FROM user_balance WHERE balance > 0")
        active = (await cursor.fetchone())[0]

        # Новых за месяц
        cursor = await db.execute("""
            SELECT COUNT(*) FROM user_balance 
            WHERE strftime('%Y-%m', updated_at) = strftime('%Y-%m', 'now')
        """)
        new_month = (await cursor.fetchone())[0]

        return {
            'total': total,
            'active': active,
            'new_month': new_month
        }


async def get_payments_statistics():
    async with aiosqlite.connect(DB_PATH) as db:
        # Общий оборот
        cursor = await db.execute("SELECT SUM(purchase_price) FROM completed_purchases")
        total_revenue = (await cursor.fetchone())[0] or 0

        # Количество пополнений
        cursor = await db.execute("SELECT COUNT(*) FROM completed_purchases")
        deposits_count = (await cursor.fetchone())[0]

        # Средний чек
        avg_check = total_revenue / deposits_count if deposits_count > 0 else 0

        # Последние платежи
        cursor = await db.execute("""
            SELECT game_name, purchase_price, purchase_date 
            FROM completed_purchases 
            ORDER BY purchase_date DESC 
            LIMIT 5
        """)
        recent_payments = await cursor.fetchall()

        return {
            'total_revenue': round(total_revenue, 2),
            'deposits_count': deposits_count,
            'avg_check': round(avg_check, 2),
            'recent_payments': recent_payments
        }


async def get_subscriptions_statistics():
    async with aiosqlite.connect(DB_PATH) as db:
        # Всего подписок
        cursor = await db.execute("SELECT COUNT(*) FROM subscriptions")
        total = (await cursor.fetchone())[0]

        # Активных подписок
        cursor = await db.execute("SELECT COUNT(*) FROM subscriptions")
        active = total  # Все подписки активны пока не сработают

        # Сработавших подписок
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT game_name) FROM completed_purchases
        """)
        triggered = (await cursor.fetchone())[0]

        # Популярные игры
        cursor = await db.execute("""
            SELECT game_name, COUNT(*) as count 
            FROM subscriptions 
            GROUP BY game_name 
            ORDER BY count DESC 
            LIMIT 5
        """)
        popular_games = await cursor.fetchall()

        return {
            'total': total,
            'active': active,
            'triggered': triggered,
            'popular_games': popular_games
        }


async def get_detailed_users_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        # Распределение по балансам
        cursor = await db.execute("""
            SELECT 
                CASE 
                    WHEN balance = 0 THEN '0 руб'
                    WHEN balance < 1000 THEN '1-1000 руб'
                    WHEN balance < 5000 THEN '1000-5000 руб'
                    ELSE '5000+ руб'
                END as balance_range,
                COUNT(*) as count
            FROM user_balance 
            GROUP BY balance_range
            ORDER BY count DESC
        """)
        balance_distribution = await cursor.fetchall()

        # Активность пользователей
        cursor = await db.execute("""
            SELECT 
                CASE 
                    WHEN DATE(updated_at) = DATE('now') THEN 'Сегодня'
                    WHEN DATE(updated_at) = DATE('now', '-1 day') THEN 'Вчера'
                    WHEN DATE(updated_at) >= DATE('now', '-7 days') THEN 'Неделя'
                    ELSE 'Ранее'
                END as activity,
                COUNT(*) as count
            FROM user_balance 
            GROUP BY activity
        """)
        user_activity = await cursor.fetchall()

        # Топ пользователей по балансу
        cursor = await db.execute("""
            SELECT user_id, balance 
            FROM user_balance 
            ORDER BY balance DESC 
            LIMIT 10
        """)
        top_users = await cursor.fetchall()

        return {
            'balance_distribution': balance_distribution,
            'user_activity': user_activity,
            'top_users': top_users
        }


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM user_balance")
        users = await cursor.fetchall()
        return [{'id': user[0]} for user in users]


import shutil
import aiosqlite
import asyncio
from datetime import datetime, timedelta
import os
import json


async def get_backup_info():
    """Информация о текущей базе данных"""
    if not os.path.exists(DB_PATH):
        return None

    db_size = os.path.getsize(DB_PATH)
    mod_time = datetime.fromtimestamp(os.path.getmtime(DB_PATH))

    async with aiosqlite.connect(DB_PATH) as db:
        # Информация о таблицах
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()

        # Количество записей в основных таблицах
        table_counts = {}
        for table in tables:
            table_name = table[0]
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = await cursor.fetchone()
            table_counts[table_name] = count[0]

    return {
        'size': db_size,
        'modified': mod_time,
        'tables': len(tables),
        'table_counts': table_counts
    }


async def create_backup(backup_type="manual"):
    """Создание бэкапа с метаданными"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    backup_filename = f"backup_{timestamp}_{backup_type}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    metadata_path = os.path.join(backup_dir, f"backup_{timestamp}_{backup_type}_meta.json")

    try:
        # Создаем копию базы данных
        original_db = await aiosqlite.connect(DB_PATH)
        backup_db = await aiosqlite.connect(backup_path)

        await original_db.backup(backup_db)
        await original_db.close()
        await backup_db.close()

        # Создаем метаданные бэкапа
        backup_info = await get_backup_info()
        metadata = {
            'filename': backup_filename,
            'created_at': datetime.now().isoformat(),
            'type': backup_type,
            'size': os.path.getsize(backup_path),
            'database_info': backup_info,
            'version': '1.0'
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

        # Очистка старых бэкапов (храним только последние 10)
        await cleanup_old_backups(backup_dir, keep_count=10)

        return {
            'success': True,
            'backup_path': backup_path,
            'metadata_path': metadata_path,
            'size': metadata['size'],
            'filename': backup_filename
        }

    except Exception as e:
        logging.error(f"Ошибка создания бэкапа: {e}")
        return {
            'success': False,
            'error': str(e)
        }


async def cleanup_old_backups(backup_dir, keep_count=10):
    """Очистка старых бэкапов"""
    try:
        backup_files = []
        for file in os.listdir(backup_dir):
            if file.startswith('backup_') and file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
                mod_time = os.path.getmtime(file_path)
                backup_files.append((file_path, mod_time))

        # Сортируем по времени изменения (новые первыми)
        backup_files.sort(key=lambda x: x[1], reverse=True)

        # Удаляем старые бэкапы
        for file_path, _ in backup_files[keep_count:]:
            os.remove(file_path)
            # Удаляем соответствующий metadata файл
            meta_file = file_path.replace('.db', '_meta.json')
            if os.path.exists(meta_file):
                os.remove(meta_file)

    except Exception as e:
        logging.error(f"Ошибка очистки бэкапов: {e}")


async def get_backup_list():
    """Получить список всех бэкапов"""
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        return []

    backups = []
    for file in os.listdir(backup_dir):
        if file.startswith('backup_') and file.endswith('.db'):
            file_path = os.path.join(backup_dir, file)
            meta_file = file_path.replace('.db', '_meta.json')

            backup_info = {
                'filename': file,
                'path': file_path,
                'size': os.path.getsize(file_path),
                'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
            }

            # Добавляем метаданные если есть
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        backup_info['metadata'] = json.load(f)
                except:
                    backup_info['metadata'] = None

            backups.append(backup_info)

    # Сортируем по дате (новые первыми)
    backups.sort(key=lambda x: x['modified'], reverse=True)
    return backups


async def restore_backup(backup_filename):
    """Восстановление из бэкапа"""
    try:
        backup_path = os.path.join("backups", backup_filename)
        if not os.path.exists(backup_path):
            return {'success': False, 'error': 'Бэкап не найден'}

        # Создаем резервную копию текущей базы
        current_backup = await create_backup("pre_restore")

        # Заменяем текущую базу бэкапом
        shutil.copy2(backup_path, DB_PATH)

        return {
            'success': True,
            'message': f'База восстановлена из {backup_filename}',
            'pre_restore_backup': current_backup['filename'] if current_backup['success'] else None
        }

    except Exception as e:
        logging.error(f"Ошибка восстановления бэкапа: {e}")
        return {'success': False, 'error': str(e)}


from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    # Устанавливаем webhook
    await bot.set_webhook(
        url=f"{"WEBHOOK_HOST"}/webhook",
        secret_token="WEBHOOK_SECRET",
        drop_pending_updates=True
    )

    # Логируем запуск
    logging.info("Bot started in webhook mode")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    # Удаляем webhook
    await bot.delete_webhook()
    logging.info("Bot stopped")


def main():
    # Настройка логирования
    setup_logging()

    if logging.DEBUG:
        # Режим разработки - polling
        asyncio.run(dp.start_polling(bot))
    else:
        # Продакшен режим - webhook
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token="WEBHOOK_SECRET",
        )

        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        # Запускаем aiohttp сервер
        web.run_app(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()