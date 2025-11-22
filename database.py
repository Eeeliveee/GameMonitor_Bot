import aiosqlite
import os

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