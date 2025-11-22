import aiohttp
import json

# Глобальная переменная для курса
current_rate = 80.81  # Ставим актуальный курс из твоего лога


async def get_usd_to_rub_rate():
    """Получает курс или использует кешированный"""
    global current_rate

    try:
        # Используем работающий API из твоего лога
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    'https://api.exchangerate-api.com/v4/latest/USD',
                    timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    new_rate = data['rates']['RUB']  # Правильный ключ!
                    print(f"✅ Курс обновлен: {new_rate} RUB")
                    current_rate = new_rate
                    return new_rate
    except Exception as e:
        print(f"⚠️ Ошибка обновления курса: {e}")
        print(f"⚠️ Использую кешированный курс: {current_rate}")

    return current_rate


async def convert_usd_to_rub(usd_amount):
    """Конвертирует USD в RUB по актуальному курсу"""
    rate = await get_usd_to_rub_rate()
    result = usd_amount * rate
    print(f"💱 Конвертация: {usd_amount} USD × {rate} RUB = {result} RUB")
    return round(result, 2)


async def force_update_rate():
    """Принудительное обновление курса"""
    global current_rate
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    'https://api.exchangerate-api.com/v4/latest/USD',
                    timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    new_rate = data['rates']['RUB']  # Правильный ключ!
                    print(f"🔄 Курс принудительно обновлен: {new_rate} RUB")
                    current_rate = new_rate
                    return new_rate
    except Exception as e:
        print(f"❌ Ошибка принудительного обновления: {e}")
    return current_rate