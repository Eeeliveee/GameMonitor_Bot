import aiohttp
import json


async def get_usd_to_rub_rate():
    """Получение курса с обходом блокировок"""

    # Список максимально простых и надежных API
    simple_apis = [
        # Самый простой API - возвращает чистый JSON
        {
            'url': 'https://api.exchangerate.host/latest?base=USD&symbols=RUB',
            'parser': lambda data: data['rates']['RUB']
        },
        # Резервный - тоже простой
        {
            'url': 'https://open.er-api.com/v6/latest/USD',
            'parser': lambda data: data['rates']['RUB']
        }
    ]

    for api in simple_apis:
        try:
            print(f"🔄 Пробую: {api['url']}")

            # Упрощенные настройки
            connector = aiohttp.TCPConnector(verify_ssl=False)
            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={'User-Agent': 'Mozilla/5.0'}
            ) as session:

                async with session.get(api['url']) as response:
                    print(f"📡 Статус: {response.status}")

                    if response.status == 200:
                        text = await response.text()
                        print(f"📄 Ответ: {text[:200]}...")  # Первые 200 символов

                        data = json.loads(text)
                        rub_rate = api['parser'](data)
                        print(f"✅ Курс: {rub_rate}")
                        return float(rub_rate)

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            continue

    # Если ничего не работает - используем курс ЦБ РФ (ручной парсинг)
    try:
        print("🔄 Пробую ЦБ РФ...")
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.cbr-xml-daily.ru/daily_json.js') as response:
                if response.status == 200:
                    text = await response.text()
                    # Простой парсинг без regex
                    start = text.find('"USD"')
                    if start != -1:
                        value_start = text.find('"Value":', start) + 8
                        value_end = text.find(',', value_start)
                        rate_str = text[value_start:value_end].strip()
                        rate = float(rate_str)
                        print(f"✅ Курс ЦБ: {rate}")
                        return rate
    except Exception as e:
        print(f"❌ ЦБ РФ: {e}")

    print("⚠️ Все методы недоступны, курс 95.0")
    return 95.0


async def convert_usd_to_rub(usd_amount):
    rate = await get_usd_to_rub_rate()
    return round(usd_amount * rate, 2)