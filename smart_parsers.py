import aiohttp
import json

# Импортируем РАБОЧУЮ функцию конвертации
from .dynamic_currency import convert_usd_to_rub


async def parse_epic_via_cheapshark(game_name):
    """CheapShark API с УМНЫМ сравнением названий"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    print(f"🔍 Ищем в CheapShark: '{game_name}'")

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            search_url = f"https://www.cheapshark.com/api/1.0/games?title={game_name}&limit=10"
            async with session.get(search_url) as response:
                if response.status == 200:
                    games = await response.json()
                    print(f"🎯 CheapShark нашел {len(games)} игр")

                    # Нормализуем поисковый запрос
                    search_normalized = game_name.lower().replace('.', '').replace('-', ' ').replace(':', '')

                    best_match = None
                    best_score = 0

                    for i, game in enumerate(games):
                        game_title = game['external']
                        game_normalized = game_title.lower().replace('.', '').replace('-', ' ').replace(':', '')

                        # Вычисляем score совпадения
                        score = 0

                        # Точное совпадение
                        if search_normalized == game_normalized:
                            score += 100

                        # Поисковый запрос содержится в названии
                        if search_normalized in game_normalized:
                            score += 50

                        # Название игры содержится в поисковом запросе
                        if game_normalized in search_normalized:
                            score += 30

                        # Совпадение по ключевым словам
                        search_words = set(search_normalized.split())
                        game_words = set(game_normalized.split())
                        common_words = search_words.intersection(game_words)
                        if common_words:
                            score += len(common_words) * 10

                        print(f"  {i + 1}. '{game_title}'")
                        print(f"     Score: {score}")

                        if score > best_score:
                            best_score = score
                            best_match = game

                    # Если нашли хорошее совпадение (score > 20)
                    if best_match and best_score > 20:
                        game_title = best_match['external']
                        game_id = best_match['gameID']
                        print(f"✅ ЛУЧШЕЕ СОВПАДЕНИЕ: '{game_title}' (score: {best_score})")

                        prices_url = f"https://www.cheapshark.com/api/1.0/games?id={game_id}"
                        async with session.get(prices_url) as prices_response:
                            if prices_response.status == 200:
                                price_data = await prices_response.json()

                                deals = price_data.get('deals', [])
                                epic_price = None
                                steam_price = None

                                print(f"📊 Найдено {len(deals)} предложений")

                                for deal in deals:
                                    store_id = deal.get('storeID')
                                    price = float(deal.get('price', 0))
                                    retail_price = float(deal.get('retailPrice', 0))

                                    # Используем розничную цену если есть, иначе обычную
                                    final_price = retail_price if retail_price > 0 else price

                                    print(f"    Магазин {store_id}: ${final_price}")

                                    rub_price = await convert_usd_to_rub(final_price)

                                    if store_id == '1':  # Steam
                                        steam_price = rub_price
                                    elif store_id == '25':  # Epic Games
                                        epic_price = rub_price

                                result = {}
                                if steam_price:
                                    result['steam'] = round(steam_price, 2)
                                if epic_price:
                                    result['epic'] = round(epic_price, 2)

                                print(f"🎯 ИТОГОВЫЕ ЦЕНЫ: {result}")
                                return result
                    else:
                        print("❌ Не найдено достаточно хороших совпадений")

        return None

    except Exception as e:
        print(f"❌ Ошибка CheapShark API: {e}")
        return None