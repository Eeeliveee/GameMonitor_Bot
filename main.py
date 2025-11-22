import asyncio
import logging
from datetime import datetime

import aiosqlite
from aiofiles import os

from parsers.epic_parser import parse_epic_price
from parsers.gog_parser import parse_gog_price
from parsers.___init___ import parse_game_price
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, FSInputFile
import database as db
from parsers.steam_parser import parse_steam_price

# Конфигурация
API_TOKEN = ""

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ОСНОВНАЯ КЛАВИАТУРА
# ОСНОВНАЯ КЛАВИАТУРА
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Добавить игру"), KeyboardButton(text="📊 Мои подписки")],
        [KeyboardButton(text="🔍 Проверить цены"), KeyboardButton(text="❌ Удалить игру")],
        [KeyboardButton(text="🤖 Авто-покупки"), KeyboardButton(text="💳 Баланс")]  # ЗАМЕНИЛ ПРЕМИУМ НА БАЛАНС
    ],
    resize_keyboard=True
)

# КЛАВИАТУРА ДЛЯ АВТО-ПОКУПОК
auto_buy_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎯 Добавить авто-покупку"), KeyboardButton(text="📋 Мои авто-правила")],
        [KeyboardButton(text="⏸️ Остановить правило"), KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)


async def background_price_checker():
    while True:
        try:
            async with aiosqlite.connect(db.DB_PATH) as conn:
                cursor = await conn.execute("SELECT user_id, game_name, target_price FROM subscriptions")
                subscriptions = await cursor.fetchall()

            for sub in subscriptions:
                user_id, game_name, target_price = sub

                # Проверяем цены на ВСЕХ площадках
                prices = await parse_game_price(game_name, "all")

                # Ищем площадки где цена ниже цели
                cheap_platforms = []
                for platform, price in prices.items():
                    if price and price <= target_price:
                        cheap_platforms.append((platform, price))

                if cheap_platforms:
                    platforms_text = ", ".join([f"{p[0].upper()} ({p[1]} руб)" for p in cheap_platforms])

                    await bot.send_message(
                        user_id,
                        f"🚨 **СЛИВ НАХУЙ!** 🚨\n"
                        f"Игра: {game_name}\n"
                        f"Цены ниже цели на: {platforms_text}\n"
                        f"Твой целевой порог: {target_price} руб\n\n"
                        f"БЕГИ ПОКУПАТЬ, ПОКА НЕ ПЕРЕХВАТИЛИ!",
                        parse_mode="HTML"
                    )

                    async with aiosqlite.connect(db.DB_PATH) as conn2:
                        await conn2.execute("DELETE FROM subscriptions WHERE user_id = ? AND game_name = ?",
                                            (user_id, game_name))
                        await conn2.commit()

        except Exception as e:
            logging.error(f"Ошибка в фоновой проверке: {e}")

        await asyncio.sleep(120)


async def background_auto_buy_checker():
    while True:
        try:
            rules = await db.get_active_auto_buy_rules()

            for rule in rules:
                # Парсим цены для конкретной платформы из правила
                prices = await parse_game_price(rule['game_name'], rule['platform'])

                current_price = prices.get(rule['platform']) if prices else None

                if current_price and current_price <= rule['max_price']:
                    await process_auto_purchase(rule, current_price)

        except Exception as e:
            logging.error(f"Ошибка в авто-покупках: {e}")

        await asyncio.sleep(60)

async def process_auto_purchase(rule, current_price):
    try:
        user_balance = await db.get_user_balance(rule['user_id'])

        if user_balance < current_price:
            await bot.send_message(
                rule['user_id'],
                f"❌ <b>Недостаточно средств для авто-покупки</b>\n\n"
                f"🎮 Игра: {rule['game_name']}\n"
                f"💰 Требуется: {current_price} руб\n"
                f"💳 Ваш баланс: {user_balance} руб\n\n"
                f"Пополните баланс для выполнения покупки!",
                parse_mode="HTML"
            )
            return

        purchase_success = await emulate_purchase(rule['game_name'], current_price)
        if purchase_success:
            await db.update_user_balance(rule['user_id'], -current_price)

            await db.log_purchase(
                user_id=rule['user_id'],
                game_name=rule['game_name'],
                purchase_price=current_price,
                platform=rule['platform']
            )

            new_balance = await db.get_user_balance(rule['user_id'])

            await bot.send_message(
                rule['user_id'],
                f"🎉 <b>АВТО-ПОКУПКА ВЫПОЛНЕНА!</b> 🎉\n\n"
                f"🎮 Игра: {rule['game_name']}\n"
                f"💰 Цена покупки: {current_price} руб\n"
                f"💳 Новый баланс: {new_balance} руб\n"
                f"🖥️ Платформа: {rule['platform']}\n\n"
                f"<i>Игра добавлена в вашу библиотеку!</i>",
                parse_mode="HTML"
            )

            await db.disable_auto_buy_rule(rule['id'])

    except Exception as e:
        logging.error(f"Ошибка при авто-покупке: {e}")

async def emulate_purchase(game_name, price):
    """Эмуляция покупки (заглушка)"""
    await asyncio.sleep(1)
    return True


# ОСНОВНЫЕ ОБРАБОТЧИКИ
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await db.create_tables()
    await message.answer(
        "🎯 <b>Game Price Monitor</b>\n\n"
        "Я отслеживаю цены на игры в Steam, Epic Games и других магазинах.\n"
        "Добавь игры для отслеживания и получи уведомление при падении цены!",
        reply_markup=main_kb,
        parse_mode="HTML"
    )


@dp.message(F.text == "🎮 Добавить игру")
async def add_game_handler(message: types.Message):
    await message.answer(
        "Введите название игры и желаемую цену в формате:\n"
        "<code>Название игры | 1000</code>\n\n"
        "Пример: <code>Cyberpunk 2077 | 1500</code>",
        parse_mode="HTML"
    )


@dp.message(F.text == "📊 Мои подписки")
async def list_subscriptions_handler(message: types.Message):
    subscriptions = await db.get_user_subscriptions(message.from_user.id)
    if not subscriptions:
        await message.answer("У вас пока нет активных подписок.")
        return

    text = "📋 <b>Ваши подписки:</b>\n\n"
    for sub in subscriptions:
        text += f"• {sub['game_name']} - до {sub['target_price']} руб.\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "🔍 Проверить цены")
async def check_prices_handler(message: types.Message):
    await message.answer("🔍 Запускаю проверку цен на всех площадках...")

    subscriptions = await db.get_user_subscriptions(message.from_user.id)
    if not subscriptions:
        await message.answer("У вас нет активных подписок для проверки.")
        return

    for sub in subscriptions:
        game_name = sub['game_name']
        target_price = sub['target_price']

        # Парсим цены со ВСЕХ площадок
        prices = await parse_game_price(game_name, "all")

        if prices:
            text = f"🎮 <b>{game_name}</b>\n\n"

            for platform, price in prices.items():
                status = "✅ НИЖЕ ЦЕЛИ!" if price <= target_price else "❌ Выше цели"
                platform_icon = {
                    "steam": "🟦",
                    "epic": "🟪",
                    "gog": "🟨"
                }.get(platform, "🟥")

                text += f"{platform_icon} {platform.upper()}: {price} руб - {status}\n"

            text += f"\n🎯 Ваша цель: {target_price} руб"

            await message.answer(text, parse_mode="HTML")
        else:
            await message.answer(f"❌ Не удалось получить цены для {game_name}")

        await asyncio.sleep(2)  # Задержка между запросами

@dp.message(F.text == "❌ Удалить игру")
async def delete_game_handler(message: types.Message):
    subscriptions = await db.get_user_subscriptions(message.from_user.id)
    if not subscriptions:
        await message.answer("У вас нет активных подписок для удаления.")
        return

    buttons = []
    for sub in subscriptions:
        buttons.append([KeyboardButton(text=f"🗑️ {sub['game_name']}")])
    buttons.append([KeyboardButton(text="🔙 Назад")])

    delete_kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

    await message.answer("Выберите игру для удаления:", reply_markup=delete_kb)


@dp.message(F.text.startswith("🗑️"))
async def process_game_delete(message: types.Message):
    game_name = message.text.replace("🗑️ ", "").strip()

    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND game_name = ?",
            (message.from_user.id, game_name)
        )
        await conn.commit()

    await message.answer(
        f"✅ Игра <b>{game_name}</b> удалена из отслеживания!",
        parse_mode="HTML",
        reply_markup=main_kb
    )


# АВТО-ПОКУПКИ
@dp.message(F.text == "🤖 Авто-покупки")
async def auto_buy_menu(message: types.Message):
    await message.answer(
        "🤖 <b>АВТОМАТИЧЕСКИЕ ПОКУПКИ</b>\n\n"
        "Бот будет автоматически покупать игры по твоим правилам!\n"
        "Просто задай игру и максимальную цену - я всё сделаю сам!",
        reply_markup=auto_buy_kb,
        parse_mode="HTML"
    )


@dp.message(F.text == "🎯 Добавить авто-покупку")
async def add_auto_buy_rule_handler(message: types.Message):
    await message.answer(
        "🎯 <b>Добавление правила авто-покупки</b>\n\n"
        "Введите данные в формате:\n"
        "<code>Название игры | Макс цена | Платформа</code>\n\n"
        "Примеры:\n"
        "<code>Cyberpunk 2077 | 1500 | steam</code>\n"
        "<code>GTA V | 800 | epic</code>\n"
        "<code>The Witcher 3 | 500 | gog</code>",
        parse_mode="HTML"
    )


@dp.message(F.text == "📋 Мои авто-правила")
async def list_auto_buy_rules(message: types.Message):
    rules = await db.get_user_auto_buy_rules(message.from_user.id)

    if not rules:
        await message.answer("У вас нет активных правил авто-покупки.")
        return

    text = "📋 <b>Ваши правила авто-покупки:</b>\n\n"
    for rule in rules:
        status = "✅ Активно" if rule['is_active'] else "⏸️ Остановлено"
        text += f"🎮 {rule['game_name']}\n"
        text += f"💰 До {rule['max_price']} руб | {rule['platform']}\n"
        text += f"🆔 ID: {rule['id']} | {status}\n\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text.contains("|"))
async def handle_pipe_messages(message: types.Message):
    try:
        parts = [part.strip() for part in message.text.split("|")]

        if len(parts) == 3:
            game_name, max_price, platform = parts
            max_price = float(max_price)

            await db.add_auto_buy_rule(
                user_id=message.from_user.id,
                game_name=game_name,
                max_price=max_price,
                platform=platform.lower()
            )

            await message.answer(
                f"✅ <b>Правило авто-покупки добавлено!</b>\n\n"
                f"🎮 Игра: {game_name}\n"
                f"💰 Макс цена: {max_price} руб\n"
                f"🖥️ Платформа: {platform}\n\n"
                f"Теперь бот будет автоматически покупать эту игру при падении цены ниже {max_price} руб!",
                parse_mode="HTML",
                reply_markup=auto_buy_kb
            )

        elif len(parts) == 2:
            game_name, target_price = parts
            target_price = int(target_price)

            await db.add_subscription(
                user_id=message.from_user.id,
                game_name=game_name,
                target_price=target_price
            )

            await message.answer(
                f"✅ Игра <b>{game_name}</b> добавлена для отслеживания!\n"
                f"Я уведомлю вас, когда цена опустится ниже <b>{target_price}</b> руб.",
                parse_mode="HTML"
            )
        else:
            raise ValueError("Неверный формат")

    except (ValueError, IndexError) as e:
        await message.answer(
            "❌ Неверный формат. Используйте:\n"
            "Для подписки: <code>Название игры | 1000</code>\n"
            "Для авто-покупки: <code>Название игры | 1000 | steam</code>",
            parse_mode="HTML"
        )


@dp.message(F.text == "🔙 Назад")
async def back_handler(message: types.Message):
    await message.answer("Возвращаюсь в главное меню:", reply_markup=main_kb)


@dp.message(F.text == "💳 Баланс")
async def balance_handler(message: types.Message):
    balance = await db.get_user_balance(message.from_user.id)

    balance_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💵 Пополнить баланс"), KeyboardButton(text="📊 История операций")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"💰 <b>Ваш баланс:</b> {balance} руб\n\n"
        "Выберите действие:",
        reply_markup=balance_kb,
        parse_mode="HTML"
    )



@dp.message(F.text == "⏸️ Остановить правило")
async def stop_rule_handler(message: types.Message):
    rules = await db.get_user_auto_buy_rules(message.from_user.id)

    if not rules:
        await message.answer("У вас нет активных правил для остановки.")
        return

    text = "📋 <b>Ваши активные правила:</b>\n\n"
    active_rules = [rule for rule in rules if rule['is_active']]

    if not active_rules:
        await message.answer("У вас нет активных правил для остановки.")
        return

    for rule in active_rules:
        text += f"🎮 {rule['game_name']}\n"
        text += f"💰 До {rule['max_price']} руб | {rule['platform']}\n"
        text += f"🆔 ID: {rule['id']}\n\n"

    text += "Введите ID правила для остановки:"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text.regexp(r'^\d+$'))
async def process_stop_rule(message: types.Message):
    try:
        rule_id = int(message.text)

        rules = await db.get_user_auto_buy_rules(message.from_user.id)
        rule_exists = any(rule['id'] == rule_id for rule in rules)

        if rule_exists:
            await db.disable_auto_buy_rule(rule_id)
            await message.answer(
                f"✅ Правило #{rule_id} остановлено!",
                reply_markup=auto_buy_kb
            )
        else:
            await message.answer(
                "❌ Правило с таким ID не найдено или вам не принадлежит",
                reply_markup=auto_buy_kb
            )

    except ValueError:
        await message.answer(
            "❌ Введите корректный ID правила (только цифры)",
            reply_markup=auto_buy_kb
        )


@dp.message(F.text == "💳 Пополнить баланс")
async def deposit_handler(message: types.Message):
    deposit_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💵 500 руб"), KeyboardButton(text="💵 1000 руб")],
            [KeyboardButton(text="💵 3000 руб"), KeyboardButton(text="💵 5000 руб")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

    balance = await db.get_user_balance(message.from_user.id)

    await message.answer(
        f"💰 <b>Ваш баланс:</b> {balance} руб\n\n"
        "Выберите сумму для пополнения:",
        reply_markup=deposit_kb,
        parse_mode="HTML"
    )


@dp.message(F.text.in_(["💵 500 руб", "💵 1000 руб", "💵 3000 руб", "💵 5000 руб"]))
async def process_deposit(message: types.Message):
    try:
        amount_text = message.text.replace("💵", "").replace("руб", "").strip()
        amount = int(amount_text)

        await db.update_user_balance(message.from_user.id, amount)

        new_balance = await db.get_user_balance(message.from_user.id)

        await message.answer(
            f"✅ Баланс пополнен на {amount} руб!\n"
            f"💰 Новый баланс: {new_balance} руб",
            reply_markup=main_kb
        )

    except ValueError:
        await message.answer(
            "❌ Ошибка при обработке платежа",
            reply_markup=main_kb
        )


@dp.message(F.text == "📊 История операций")
async def transaction_history_handler(message: types.Message):
    transactions = await db.get_user_transactions(message.from_user.id)

    if not transactions:
        await message.answer("У вас еще нет операций.")
        return

    text = "📊 <b>История операций:</b>\n\n"
    for transaction in transactions[:10]:
        if transaction['type'] == 'purchase':
            text += f"🛒 {transaction['game_name']}\n"
            text += f"💸 -{transaction['amount']} руб | {transaction['platform']}\n"
            text += f"📅 {transaction['date'][:16]}\n\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "💵 Пополнить баланс")
async def show_deposit_options(message: types.Message):
    deposit_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💵 500 руб"), KeyboardButton(text="💵 1000 руб")],
            [KeyboardButton(text="💵 3000 руб"), KeyboardButton(text="💵 5000 руб")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

    balance = await db.get_user_balance(message.from_user.id)

    await message.answer(
        f"💰 <b>Ваш баланс:</b> {balance} руб\n\n"
        "Выберите сумму для пополнения:",
        reply_markup=deposit_kb,
        parse_mode="HTML"
    )


@dp.message(Command("price"))
async def check_specific_game(message: types.Message):
    if len(message.text.split()) < 2:
        await message.answer("Использование: /price <название игры>")
        return

    game_name = message.text.split(' ', 1)[1]
    await message.answer(f"🔍 Ищу цены на {game_name}...")

    prices = await parse_game_price(game_name, "all")

    if prices:
        text = f"🎮 <b>{game_name}</b>\n\n"

        for platform, price in prices.items():
            platform_icon = {
                "steam": "🟦",
                "epic": "🟪",
                "gog": "🟨"
            }.get(platform, "🟥")

            text += f"{platform_icon} {platform.upper()}: {price} руб\n"

        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(f"❌ Не удалось найти цены для {game_name}")


@dp.message(Command("test_price"))
async def test_price_handler(message: types.Message):
    if len(message.text.split()) < 2:
        await message.answer("Использование: /test_price <название игры>")
        return

    game_name = message.text.split(' ', 1)[1]

    await message.answer(f"🧪 Тестирую парсеры для: {game_name}")

    # Тестируем каждый парсер отдельно
    steam_price = await parse_steam_price(game_name)
    epic_price = await parse_epic_price(game_name)
    gog_price = await parse_gog_price(game_name)

    text = f"🎮 <b>{game_name}</b>\n\n"
    text += f"🟦 Steam: {steam_price if steam_price else '❌'} руб\n"
    text += f"🟪 Epic: {epic_price if epic_price else '❌'} руб\n"
    text += f"🟨 GOG: {gog_price if gog_price else '❌'} руб\n"

    await message.answer(text, parse_mode="HTML")


# Временно добавь эту функцию в main.py для теста
@dp.message(Command("test_ire"))
async def test_ire_handler(message: types.Message):
    """Тест конкретной игры Ire: A Prologue"""
    from parsers.___init___ import parse_game_price

    prices = await parse_game_price("Ire: A Prologue", "all")

    text = "🎮 <b>Ire: A Prologue - ТЕСТ</b>\n\n"
    for platform, price in prices.items():
        text += f"{platform.upper()}: {price} руб\n"

    text += f"\nРеальные цены:\nSteam: 710 руб\nEpic: 600 руб"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("add_price"))
async def add_manual_price(message: types.Message):
    """Добавить игру в ручную базу цен"""
    try:
        # Формат: /add_price "Ire: A Prologue" steam=710 epic=600
        parts = message.text.split('"')
        if len(parts) < 3:
            await message.answer('Формат: /add_price "Название игры" steam=710 epic=600')
            return

        game_name = parts[1]
        price_text = parts[2].strip()

        # Парсим цены
        prices = {}
        for part in price_text.split():
            if '=' in part:
                platform, price = part.split('=')
                prices[platform.lower()] = float(price)

        # Здесь можно сохранить в базу данных
        # Пока просто выводим
        text = f"✅ Добавлены цены для {game_name}:\n"
        for platform, price in prices.items():
            text += f"{platform}: {price} руб\n"

        await message.answer(text)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("test_smart"))
async def test_smart_parser(message: types.Message):
    """Тест умного парсера"""
    if len(message.text.split()) < 2:
        await message.answer("Использование: /test_smart <название игры>")
        return

    game_name = message.text.split(' ', 1)[1]

    from parsers.___init___ import parse_game_price
    prices = await parse_game_price(game_name, "all")

    text = f"🎮 <b>{game_name}</b>\n\n"
    for platform, price in prices.items():
        text += f"{platform.upper()}: {price} руб\n"

    if not prices:
        text += "❌ Не удалось получить цены"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("курс"))
async def exchange_rate_handler(message: types.Message):
    """Показать текущий курс валют"""
    try:
        from parsers.dynamic_currency import get_usd_to_rub_rate

        rate = await get_usd_to_rub_rate()

        await message.answer(
            f"💱 <b>Текущий курс:</b>\n"
            f"🇺🇸 1 USD = {rate} RUB\n\n"
            f"<i>Курс обновляется автоматически</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {e}",
            parse_mode="HTML"
        )


@dp.message(Command("обновить_курс"))
async def update_rate_handler(message: types.Message):
    """Принудительно обновить курс"""
    try:
        from parsers.dynamic_currency import force_update_rate
        rate = await force_update_rate()

        await message.answer(
            f"🔄 <b>Курс обновлен:</b>\n"
            f"🇺🇸 1 USD = {rate} RUB",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка обновления:</b> {e}",
            parse_mode="HTML"
        )


@dp.message(Command("тест_конвертации"))
async def test_conversion_handler(message: types.Message):
    """Тест конвертации цен"""
    try:
        from parsers.dynamic_currency import convert_usd_to_rub

        # Тестируем конвертацию разных сумм
        test_amounts = [1.0, 10.0, 19.99, 59.99]

        text = "🧪 <b>Тест конвертации USD → RUB:</b>\n\n"

        for usd in test_amounts:
            rub = await convert_usd_to_rub(usd)
            text += f"💵 {usd} USD = {rub} RUB\n"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Ошибка теста: {e}")

@dp.message(Command("курс_детально"))
async def detailed_rate_handler(message: types.Message):
    """Детальная диагностика курса"""
    try:
        from parsers.simple_currency import get_usd_to_rub_rate
        rate = await get_usd_to_rub_rate()

        await message.answer(
            f"🔧 <b>Детальная диагностика курса:</b>\n"
            f"🇺🇸 1 USD = {rate} RUB\n\n"
            f"<i>Проверь консоль бота для подробного лога</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {e}",
            parse_mode="HTML"
        )


@dp.message(Command("stalker_deep_debug"))
async def stalker_deep_debug_handler(message: types.Message):
    """Глубокий дебаг Stalker 2"""
    import aiohttp
    from parsers.dynamic_currency import convert_usd_to_rub

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    debug_text = "🔍 <b>ГЛУБОКИЙ ДЕБАГ STALKER 2:</b>\n\n"

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # Ищем игру
            search_url = "https://www.cheapshark.com/api/1.0/games?title=STALKER%202&limit=10"
            async with session.get(search_url) as response:
                if response.status == 200:
                    games = await response.json()
                    debug_text += f"🎯 <b>Найдено игр:</b> {len(games)}\n"

                    for i, game in enumerate(games):
                        debug_text += f"\n<b>Игра #{i + 1}:</b>\n"
                        debug_text += f"Название: {game['external']}\n"
                        debug_text += f"ID: {game['gameID']}\n"
                        debug_text += f"Самая низкая цена: ${game.get('cheapest', 'N/A')}\n"

                        # Получаем детали по каждой игре
                        prices_url = f"https://www.cheapshark.com/api/1.0/games?id={game['gameID']}"
                        async with session.get(prices_url) as prices_response:
                            if prices_response.status == 200:
                                price_data = await prices_response.json()
                                deals = price_data.get('deals', [])

                                debug_text += f"Найдено предложений: {len(deals)}\n"

                                for j, deal in enumerate(deals[:3]):  # Первые 3 предложения
                                    debug_text += f"\n  <b>Предложение #{j + 1}:</b>\n"
                                    debug_text += f"  Магазин ID: {deal.get('storeID')}\n"
                                    debug_text += f"  Цена: ${deal.get('price')}\n"
                                    debug_text += f"  Розничная цена: ${deal.get('retailPrice')}\n"
                                    debug_text += f"  Экономия: {deal.get('savings', 0)}%\n"

                                    # Конвертируем в рубли
                                    usd_price = float(deal.get('price', 0))
                                    rub_price = await convert_usd_to_rub(usd_price)
                                    debug_text += f"  В рублях: {rub_price} руб\n"

        await message.answer(debug_text, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("test_conversion_deep"))
async def test_conversion_deep_handler(message: types.Message):
    """Глубокий тест конвертации"""
    from parsers.dynamic_currency import convert_usd_to_rub

    test_amounts = [1.0, 10.0, 59.99, 69.99]

    text = "🧪 <b>ГЛУБОКИЙ ТЕСТ КОНВЕРТАЦИИ:</b>\n\n"

    for usd in test_amounts:
        rub = await convert_usd_to_rub(usd)
        text += f"💵 ${usd} = {rub} руб\n"

    text += f"\n📊 <b>Stalker 2 должен стоить:</b>\n"
    text += f"💵 $59.99 = {await convert_usd_to_rub(59.99)} руб\n"
    text += f"💵 $69.99 = {await convert_usd_to_rub(69.99)} руб\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("debug_parsers"))
async def debug_parsers_handler(message: types.Message):
    """Детальный дебаг всех парсеров"""
    from parsers.___init___ import parse_game_price

    game_name = "STALKER 2"
    print(f"\n" + "=" * 50)
    print(f"🔍 ЗАПУСК ДЕТАЛЬНОГО ДЕБАГА ДЛЯ: '{game_name}'")
    print("=" * 50)

    prices = await parse_game_price(game_name, "all")

    text = f"🎮 <b>РЕЗУЛЬТАТ ДЛЯ '{game_name}':</b>\n\n"
    for platform, price in prices.items():
        text += f"🟦 {platform.upper()}: {price} руб\n"

    text += f"\n📊 <b>Ожидаемые цены:</b> ~4000-5000 руб\n"
    text += f"<i>Проверь консоль для полного лога парсеров</i>"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("test_fixed"))
async def test_fixed_handler(message: types.Message):
    """Тест исправленных парсеров"""
    from parsers.___init___ import parse_game_price

    test_games = [
        "STALKER 2",
        "S.T.A.L.K.E.R. 2",
        "Stalker 2 Heart of Chornobyl",
        "S.T.A.L.K.E.R. 2: Heart of Chornobyl"
    ]

    for game_name in test_games:
        print(f"\n" + "=" * 50)
        print(f"🔍 ТЕСТ: '{game_name}'")
        print("=" * 50)

        prices = await parse_game_price(game_name, "all")

        text = f"🎮 <b>'{game_name}':</b>\n"
        for platform, price in prices.items():
            text += f"🟦 {platform.upper()}: {price} руб\n"

        if not prices:
            text += "❌ Не найдено цен\n"

        await message.answer(text, parse_mode="HTML")
        await asyncio.sleep(1)


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandObject

# Список администраторов (замени на свои ID)
ADMIN_IDS = [123456789, 987654321]  # Твои ID через запятую


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен")
        return

    # Получаем статистику
    user_count = await db.get_user_count()
    total_revenue = await db.get_total_revenue()
    active_subs = await db.get_active_subscriptions()
    today_users = await db.get_today_users()

    # Создаем клавиатуру для быстрых действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance"),
            InlineKeyboardButton(text="🎮 Подписки", callback_data="admin_subs")
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🔄 Бэкап", callback_data="admin_backup")
        ]
    ])

    text = f"""
🛠 <b>Админ-панель | GameMonitor Bot</b>

👥 <b>Пользователи:</b>
   Всего: <code>{user_count}</code>
   Новые сегодня: <code>{today_users}</code>

💰 <b>Финансы:</b>
   Общий оборот: <code>{total_revenue} руб</code>
   Активные подписки: <code>{active_subs}</code>

⚙️ <b>Быстрые действия:</b>
"""
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# Обработчики кнопок админ-панели
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, [])


@dp.callback_query(F.data == "admin_users")
async def admin_users_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, ["users"])


@dp.callback_query(F.data == "admin_finance")
async def admin_finance_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, ["payments"])


@dp.callback_query(F.data == "admin_subs")
async def admin_subs_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, ["subs"])


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Используйте команду:\n"
        "<code>/broadcast Ваш текст сообщения</code>\n\n"
        "Или:\n"
        "<code>/broadcast_test Тестовое сообщение</code>",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin_backup")
async def admin_backup_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💾 <b>Управление бэкапами</b>\n\n"
        "Команды:\n"
        "<code>/backup</code> - создать бэкап\n"
        "<code>/backup list</code> - список бэкапов\n"
        "<code>/backup auto</code> - настройка авто-бэкапов",
        parse_mode="HTML"
    )


async def show_statistics(message: types.Message, args: list):
    """Показать статистику в зависимости от аргументов"""

    if not args:
        # Общая статистика
        users_stats = await db.get_users_statistics()
        payments_stats = await db.get_payments_statistics()
        subs_stats = await db.get_subscriptions_statistics()

        text = f"""
📊 <b>Общая статистика</b>

👥 <b>Пользователи:</b>
   Всего: <code>{users_stats['total']}</code>
   Активных: <code>{users_stats['active']}</code>
   Новых за месяц: <code>{users_stats['new_month']}</code>

💰 <b>Финансы:</b>
   Общий оборот: <code>{payments_stats['total_revenue']} руб</code>
   Средний чек: <code>{payments_stats['avg_check']} руб</code>
   Пополнений: <code>{payments_stats['deposits_count']}</code>

🎮 <b>Подписки:</b>
   Активных: <code>{subs_stats['active']}</code>
   Всего создано: <code>{subs_stats['total']}</code>
   Сработавших: <code>{subs_stats['triggered']}</code>

<b>Последние платежи:</b>
"""
        # Добавляем последние платежи
        for payment in payments_stats['recent_payments'][:3]:
            game_name, price, date = payment
            text += f"   🎮 {game_name}: {price} руб\n"

        # Клавиатура для детальной статистики
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Детально по пользователям", callback_data="stats_users_detailed"),
                InlineKeyboardButton(text="💰 Детально по финансам", callback_data="stats_payments_detailed")
            ],
            [
                InlineKeyboardButton(text="🎮 Детально по подпискам", callback_data="stats_subs_detailed"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")
            ]
        ])

    elif args[0] == "users":
        # Детальная статистика по пользователям
        users_data = await db.get_detailed_users_stats()

        text = "👥 <b>Детальная статистика по пользователям</b>\n\n"

        text += "<b>Распределение по балансам:</b>\n"
        for balance_range, count in users_data['balance_distribution']:
            text += f"   {balance_range}: {count} чел.\n"

        text += "\n<b>Активность пользователей:</b>\n"
        for activity, count in users_data['user_activity']:
            text += f"   {activity}: {count} чел.\n"

        text += "\n<b>Топ пользователей по балансу:</b>\n"
        for i, (user_id, balance) in enumerate(users_data['top_users'][:5], 1):
            text += f"   {i}. ID {user_id}: {balance} руб\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="admin_stats")]
        ])

    elif args[0] == "payments":
        # Детальная статистика по платежам
        payments_stats = await db.get_payments_statistics()

        text = "💰 <b>Детальная финансовая статистика</b>\n\n"

        text += f"<b>Основные метрики:</b>\n"
        text += f"   Общий оборот: <code>{payments_stats['total_revenue']} руб</code>\n"
        text += f"   Количество платежей: <code>{payments_stats['deposits_count']}</code>\n"
        text += f"   Средний чек: <code>{payments_stats['avg_check']} руб</code>\n"

        text += f"\n<b>Последние 5 платежей:</b>\n"
        for payment in payments_stats['recent_payments']:
            game_name, price, date = payment
            date_str = date[:16] if date else "N/A"
            text += f"   🎮 {game_name}: {price} руб ({date_str})\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="admin_stats")]
        ])

    elif args[0] == "subs":
        # Детальная статистика по подпискам
        subs_stats = await db.get_subscriptions_statistics()

        text = "🎮 <b>Детальная статистика по подпискам</b>\n\n"

        text += f"<b>Основные метрики:</b>\n"
        text += f"   Всего подписок: <code>{subs_stats['total']}</code>\n"
        text += f"   Активных: <code>{subs_stats['active']}</code>\n"
        text += f"   Сработавших: <code>{subs_stats['triggered']}</code>\n"

        text += f"\n<b>Популярные игры для отслеживания:</b>\n"
        for i, (game_name, count) in enumerate(subs_stats['popular_games'][:5], 1):
            text += f"   {i}. {game_name}: {count} подписок\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="admin_stats")]
        ])

    else:
        text = "❌ Неизвестный раздел статистики"
        keyboard = None

    if hasattr(message, 'edit_text'):
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.message(Command("statistics"))
async def statistics_handler(message: types.Message, command: CommandObject = None):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен")
        return

    args = command.args.split() if command and command.args else []
    await show_statistics(message, args)


# Обработчики для детальной статистики
@dp.callback_query(F.data == "stats_users_detailed")
async def stats_users_detailed_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, ["users"])


@dp.callback_query(F.data == "stats_payments_detailed")
async def stats_payments_detailed_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, ["payments"])


@dp.callback_query(F.data == "stats_subs_detailed")
async def stats_subs_detailed_handler(callback: CallbackQuery):
    await callback.answer()
    await show_statistics(callback.message, ["subs"])


import asyncio
import schedule
import time
from threading import Thread


class BackupManager:
    def __init__(self):
        self.auto_backup_enabled = True
        self.backup_schedule = "03:00"  # Каждый день в 3:00

    async def start_auto_backups(self):
        """Запуск автоматических бэкапов"""
        if not self.auto_backup_enabled:
            return

        def run_scheduler():
            schedule.every().day.at(self.backup_schedule).do(
                lambda: asyncio.create_task(self.create_auto_backup())
            )

            while True:
                schedule.run_pending()
                time.sleep(60)

        # Запускаем в отдельном потоке
        thread = Thread(target=run_scheduler, daemon=True)
        thread.start()
        logging.info(f"Автоматические бэкапы запущены (расписание: {self.backup_schedule})")

    async def create_auto_backup(self):
        """Создание автоматического бэкапа"""
        try:
            result = await db.create_backup("auto")
            if result['success']:
                logging.info(f"Авто-бэкап создан: {result['filename']}")

                # Уведомляем админов
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"✅ <b>Автоматический бэкап создан</b>\n"
                            f"Файл: {result['filename']}\n"
                            f"Размер: {result['size'] / 1024 / 1024:.2f} MB\n"
                            f"Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                            parse_mode="HTML"
                        )
                    except:
                        continue
            else:
                logging.error(f"Ошибка авто-бэкапа: {result['error']}")

        except Exception as e:
            logging.error(f"Ошибка в авто-бэкапе: {e}")


# Создаем менеджер бэкапов
backup_manager = BackupManager()


@dp.message(Command("backup"))
async def backup_handler(message: types.Message, command: CommandObject = None):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен")
        return

    args = command.args.split() if command and command.args else []

    if not args:
        # Создание бэкапа
        await message.answer("🔄 Создаю бэкап...")
        result = await db.create_backup("manual")

        if result['success']:
            file_size = result['size'] / 1024 / 1024  # MB

            # Отправляем файл бэкапа
            await message.answer_document(
                document=FSInputFile(result['backup_path']),
                caption=(
                    f"✅ <b>Бэкап создан успешно!</b>\n\n"
                    f"📁 Файл: <code>{result['filename']}</code>\n"
                    f"💾 Размер: {file_size:.2f} MB\n"
                    f"🕐 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                    f"<i>Бэкап автоматически очищаются, остаются только последние 10</i>"
                ),
                parse_mode="HTML"
            )
        else:
            await message.answer(f"❌ Ошибка создания бэкапа: {result['error']}")

    elif args[0] == "list":
        # Список бэкапов
        backups = await db.get_backup_list()

        if not backups:
            await message.answer("📂 Бэкапы не найдены")
            return

        text = "📂 <b>Список бэкапов:</b>\n\n"
        for i, backup in enumerate(backups[:10], 1):  # Показываем последние 10
            size_mb = backup['size'] / 1024 / 1024
            mod_time = backup['modified'].strftime('%d.%m.%Y %H:%M')

            text += f"{i}. <code>{backup['filename']}</code>\n"
            text += f"   📏 {size_mb:.2f} MB | 🕐 {mod_time}\n\n"

        # Клавиатура для управления бэкапами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Создать новый", callback_data="backup_create"),
                InlineKeyboardButton(text="🧹 Очистить старые", callback_data="backup_cleanup")
            ]
        ])

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    elif args[0] == "auto":
        # Управление авто-бэкапами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Включены" if backup_manager.auto_backup_enabled else "❌ Выключены",
                    callback_data="backup_toggle_auto"
                )
            ],
            [
                InlineKeyboardButton(text="🕐 Изменить расписание", callback_data="backup_change_schedule"),
                InlineKeyboardButton(text="🔄 Создать сейчас", callback_data="backup_create_auto")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_backup")
            ]
        ])

        await message.answer(
            f"🤖 <b>Автоматические бэкапы</b>\n\n"
            f"Статус: {'✅ Включены' if backup_manager.auto_backup_enabled else '❌ Выключены'}\n"
            f"Расписание: каждый день в {backup_manager.backup_schedule}\n\n"
            f"<i>Бэкапы создаются автоматически и хранятся 10 последних версий</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    elif args[0] == "restore" and len(args) > 1:
        # Восстановление из бэкапа
        backup_filename = args[1]

        # Подтверждение восстановления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"backup_restore_confirm:{backup_filename}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="backup_cancel")
            ]
        ])

        await message.answer(
            f"🔄 <b>Подтверждение восстановления</b>\n\n"
            f"Вы собираетесь восстановить базу из:\n"
            f"<code>{backup_filename}</code>\n\n"
            f"<b>ВНИМАНИЕ:</b> Текущая база будет заменена!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# Обработчики кнопок бэкапов
@dp.callback_query(F.data == "backup_create")
async def backup_create_handler(callback: CallbackQuery):
    await callback.answer()
    await backup_handler(callback.message, CommandObject(args=""))


@dp.callback_query(F.data == "backup_toggle_auto")
async def backup_toggle_auto_handler(callback: CallbackQuery):
    backup_manager.auto_backup_enabled = not backup_manager.auto_backup_enabled
    await callback.answer(f"Авто-бэкапы {'включены' if backup_manager.auto_backup_enabled else 'выключены'}")
    await backup_handler(callback.message, CommandObject(args="auto"))


@dp.callback_query(F.data.startswith("backup_restore_confirm:"))
async def backup_restore_confirm_handler(callback: CallbackQuery):
    backup_filename = callback.data.split(":")[1]

    await callback.message.edit_text("🔄 Восстанавливаю базу...")
    result = await db.restore_backup(backup_filename)

    if result['success']:
        text = f"✅ <b>База восстановлена!</b>\n\nФайл: <code>{backup_filename}</code>"
        if result['pre_restore_backup']:
            text += f"\n\n📁 Создан бэкап перед восстановлением: <code>{result['pre_restore_backup']}</code>"
    else:
        text = f"❌ <b>Ошибка восстановления:</b>\n{result['error']}"

    await callback.message.edit_text(text, parse_mode="HTML")


class BroadcastManager:
    def __init__(self):
        self.active_broadcasts = {}
        self.broadcast_stats = {}

    async def send_broadcast(self, text, broadcast_type="text", **kwargs):
        """Отправка рассылки всем пользователям"""
        users = await db.get_all_users()
        total_users = len(users)

        # Создаем ID рассылки для отслеживания
        broadcast_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.active_broadcasts[broadcast_id] = {
            'started_at': datetime.now(),
            'total_users': total_users,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'text': text
        }

        # Клавиатура для отмены рассылки
        cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить рассылку", callback_data=f"broadcast_cancel:{broadcast_id}")]
        ])

        # Уведомляем админов о начале рассылки
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📢 <b>Начата рассылка</b>\n\n"
                    f"Текст: {text[:100]}{'...' if len(text) > 100 else ''}\n"
                    f"Получателей: {total_users}\n"
                    f"ID рассылки: <code>{broadcast_id}</code>",
                    reply_markup=cancel_keyboard,
                    parse_mode="HTML"
                )
            except:
                continue

        # Отправляем сообщения пользователям
        success_count = 0
        fail_count = 0

        for i, user in enumerate(users):
            try:
                if broadcast_type == "text":
                    await bot.send_message(user['id'], text)
                elif broadcast_type == "photo" and 'photo' in kwargs:
                    await bot.send_photo(user['id'], kwargs['photo'], caption=text)

                success_count += 1
                self.active_broadcasts[broadcast_id]['success'] = success_count

                # Anti-flood задержка
                if i % 10 == 0:  # Каждые 10 сообщений
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(0.1)

            except Exception as e:
                fail_count += 1
                self.active_broadcasts[broadcast_id]['failed'] = fail_count
                logging.error(f"Ошибка отправки пользователю {user['id']}: {e}")

            self.active_broadcasts[broadcast_id]['processed'] = i + 1

            # Обновляем прогресс каждые 50 пользователей
            if i % 50 == 0:
                await self.update_broadcast_progress(broadcast_id)

        # Завершаем рассылку
        await self.finish_broadcast(broadcast_id)
        return success_count, fail_count

    async def update_broadcast_progress(self, broadcast_id):
        """Обновление прогресса рассылки"""
        if broadcast_id not in self.active_broadcasts:
            return

        broadcast = self.active_broadcasts[broadcast_id]
        progress = (broadcast['processed'] / broadcast['total_users']) * 100

        # Можно добавить отправку прогресса админам
        # Пока просто логируем
        logging.info(f"Рассылка {broadcast_id}: {progress:.1f}%")

    async def finish_broadcast(self, broadcast_id):
        """Завершение рассылки и отправка статистики"""
        if broadcast_id not in self.active_broadcasts:
            return

        broadcast = self.active_broadcasts[broadcast_id]
        duration = datetime.now() - broadcast['started_at']

        # Сохраняем статистику
        self.broadcast_stats[broadcast_id] = {
            **broadcast,
            'finished_at': datetime.now(),
            'duration': duration.total_seconds()
        }

        # Уведомляем админов о завершении
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ <b>Рассылка завершена</b>\n\n"
                    f"ID: <code>{broadcast_id}</code>\n"
                    f"✅ Успешно: {broadcast['success']}\n"
                    f"❌ Ошибок: {broadcast['failed']}\n"
                    f"📊 Всего: {broadcast['total_users']}\n"
                    f"⏱ Длительность: {duration.total_seconds():.1f} сек\n"
                    f"📈 Успешность: {(broadcast['success'] / broadcast['total_users'] * 100):.1f}%",
                    parse_mode="HTML"
                )
            except:
                continue

        # Удаляем из активных рассылок
        del self.active_broadcasts[broadcast_id]


# Создаем менеджер рассылок
broadcast_manager = BroadcastManager()


@dp.message(Command("broadcast"))
async def broadcast_handler(message: types.Message, command: CommandObject = None):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен")
        return

    if not command or not command.args:
        await message.answer(
            "📢 <b>Система рассылок</b>\n\n"
            "Команды:\n"
            "<code>/broadcast текст</code> - текстовая рассылка\n"
            "<code>/broadcast_photo текст</code> - рассылка с фото (ответьте на фото)\n"
            "<code>/broadcast_test текст</code> - тестовая рассылка (только админам)\n"
            "<code>/broadcast_stats</code> - статистика рассылок",
            parse_mode="HTML"
        )
        return

    broadcast_text = command.args

    # Подтверждение рассылки
    users_count = await db.get_user_count()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Начать рассылку", callback_data=f"broadcast_confirm:text:{broadcast_text}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])

    await message.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"Текст: {broadcast_text}\n"
        f"Получателей: {users_count}\n\n"
        f"<i>Рассылка может занять несколько минут</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.message(Command("broadcast_photo"))
async def broadcast_photo_handler(message: types.Message, command: CommandObject = None):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.answer("❌ Ответьте на фото для рассылки с изображением")
        return

    if not command or not command.args:
        await message.answer("❌ Укажите текст подписи: /broadcast_photo ваш текст")
        return

    photo = message.reply_to_message.photo[-1]  # Берем самое качественное фото
    caption = command.args

    users_count = await db.get_user_count()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Начать рассылку",
                                 callback_data=f"broadcast_confirm:photo:{caption}:{photo.file_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])

    await message.answer(
        f"📢 <b>Подтверждение рассылки с фото</b>\n\n"
        f"Текст: {caption}\n"
        f"Получателей: {users_count}\n"
        f"Фото: {photo.file_id}\n\n"
        f"<i>Рассылка может занять несколько минут</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.message(Command("broadcast_test"))
async def broadcast_test_handler(message: types.Message, command: CommandObject = None):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not command or not command.args:
        await message.answer("❌ Укажите текст: /broadcast_test ваш текст")
        return

    test_text = command.args

    # Тестовая рассылка только админам
    success_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🧪 <b>Тестовая рассылка</b>\n\n{test_text}", parse_mode="HTML")
            success_count += 1
        except:
            pass

    await message.answer(f"✅ Тестовая рассылка отправлена {success_count} админам")


@dp.message(Command("broadcast_stats"))
async def broadcast_stats_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not broadcast_manager.broadcast_stats:
        await message.answer("📊 Статистика рассылок отсутствует")
        return

    # Статистика последних 5 рассылок
    recent_broadcasts = list(broadcast_manager.broadcast_stats.values())[-5:]

    text = "📊 <b>Статистика рассылок</b>\n\n"

    for i, broadcast in enumerate(recent_broadcasts[::-1], 1):  # Новые первыми
        success_rate = (broadcast['success'] / broadcast['total_users']) * 100
        duration_min = broadcast['duration'] / 60

        text += f"{i}. <code>{broadcast['started_at'].strftime('%d.%m %H:%M')}</code>\n"
        text += f"   ✅ {broadcast['success']} | ❌ {broadcast['failed']} | 📊 {broadcast['total_users']}\n"
        text += f"   📈 {success_rate:.1f}% | ⏱ {duration_min:.1f} мин\n"
        text += f"   💬 {broadcast['text'][:50]}{'...' if len(broadcast['text']) > 50 else ''}\n\n"

    await message.answer(text, parse_mode="HTML")


# Обработчики кнопок рассылок
@dp.callback_query(F.data.startswith("broadcast_confirm:"))
async def broadcast_confirm_handler(callback: CallbackQuery):
    data_parts = callback.data.split(":")
    broadcast_type = data_parts[1]
    text = data_parts[2]

    await callback.message.edit_text("🔄 Начинаю рассылку...")

    if broadcast_type == "text":
        success_count, fail_count = await broadcast_manager.send_broadcast(text)
    elif broadcast_type == "photo":
        photo_id = data_parts[3]
        success_count, fail_count = await broadcast_manager.send_broadcast(
            text, "photo", photo=photo_id
        )

    await callback.message.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"✅ Успешно: {success_count}\n"
        f"❌ Ошибок: {fail_count}\n"
        f"📊 Всего: {success_count + fail_count}",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("broadcast_cancel:"))
async def broadcast_cancel_handler(callback: CallbackQuery):
    broadcast_id = callback.data.split(":")[1]

    if broadcast_id in broadcast_manager.active_broadcasts:
        # Можно добавить логику отмены
        del broadcast_manager.active_broadcasts[broadcast_id]

    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer("Рассылка отменена")


@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_simple_cancel_handler(callback: CallbackQuery):
    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer()


import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Настройка системы логирования"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                os.path.join(log_dir, 'bot.log'),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            ),
            logging.StreamHandler()  # Вывод в консоль
        ]
    )


@dp.message(Command("logs"))
async def logs_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    log_type = args[0] if args else "error"

    log_file = "logs/bot.log"
    if not os.path.exists(log_file):
        await message.answer("❌ Файл логов не найден")
        return

    # Читаем последние строки логов
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        last_lines = lines[-50:]  # Последние 50 строк

    log_text = "".join(last_lines)

    if len(log_text) > 4000:  # Ограничение Telegram
        log_text = log_text[-4000:]

    await message.answer(f"📋 **Последние логи ({log_type}):**\n```\n{log_text}\n```",
                         parse_mode="Markdown")


@dp.message(Command("status"))
async def status_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    import psutil
    import datetime

    # Системная информация
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())

    # Информация о боте
    db_size = os.path.getsize(db.DB_PATH) / 1024 / 1024  # MB

    text = f"""
🖥 **Статус системы**

**Ресурсы:**
CPU: {cpu_percent}%
Память: {memory.percent}% ({memory.used // 1024 // 1024}MB/{memory.total // 1024 // 1024}MB)
Диск: {disk.percent}% ({disk.used // 1024 // 1024}MB/{disk.total // 1024 // 1024}MB)

**Бот:**
Время работы: {datetime.datetime.now() - boot_time}
Размер БД: {db_size:.2f} MB
Пользователей: {await db.get_user_count()}

**Версия:** 1.0.0
**Статус:** ✅ Активен
"""
    await message.answer(text, parse_mode="HTML")



async def main():
    logging.basicConfig(level=logging.INFO)

    # Запускаем ВСЕ фоновые задачи
    asyncio.create_task(background_price_checker())
    asyncio.create_task(background_auto_buy_checker())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())