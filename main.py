import asyncio
import logging
import aiosqlite

from parsers.epic_parser import parse_epic_price
from parsers.gog_parser import parse_gog_price
from parsers.___init___ import parse_game_price
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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

async def main():
    logging.basicConfig(level=logging.INFO)

    # Запускаем ВСЕ фоновые задачи
    asyncio.create_task(background_price_checker())
    asyncio.create_task(background_auto_buy_checker())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())