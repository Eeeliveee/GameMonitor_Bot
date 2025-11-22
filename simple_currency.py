import aiohttp
import json
import asyncio


async def get_usd_to_rub_rate():
    """Простой и надежный способ получить курс с детальным логированием"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    print("🔍 Начинаю получение курса USD/RUB...")

    # СПИСОК API ДЛЯ ПРОВЕРКИ
    apis = [
        {
            'name': 'ExchangeRate-API',
            'url': 'https://api.exchangerate-api.com/v4/latest/USD',
            'parser': lambda data: data['rates']['RUB']
        },
        {
            'name': 'Frankfurter',
            'url': 'https://api.frankfurter.app/latest?from=USD&to=RUB',
            'parser': lambda data: data['rates']['RUB']
        },
        {
            'name': 'Currency-API',
            'url': 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@1/latest/currencies/usd/rub.json',
            'parser': lambda data: data['rub']
        },
        {
            'name': 'OpenExchangeRates',
            'url': 'https://open.er-api.com/v6/latest/USD',
            'parser': lambda data: data['rates']['RUB']
        }
    ]

    for api in apis:
        try:
            print(f"🔄 Пробую {api['name']}: {api['url']}")

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(api['url']) as response:
                    print(f"📡 Статус ответа: {response.status}")

                    if response.status == 200:
                        data = await response.json()
                        print(f"📊 Получены данные: {data}")

                        rub_rate = api['parser'](data)
                        print(f"✅ {api['name']} курс: 1 USD = {rub_rate} RUB")
                        return float(rub_rate)
                    else:
                        print(f"❌ {api['name']} статус: {response.status}")

        except asyncio.TimeoutError:
            print(f"⏰ {api['name']}: Таймаут")
        except Exception as e:
            print(f"❌ {api['name']} ошибка: {e}")

    print("⚠️ Все API недоступны, использую курс по умолчанию 95.0")
    return 95.0


async def convert_usd_to_rub(usd_amount):
    """Конвертирует USD в RUB"""
    rate = await get_usd_to_rub_rate()
    result = usd_amount * rate
    print(f"💱 Конвертация: {usd_amount} USD × {rate} = {result} RUB")
    return round(result, 2)