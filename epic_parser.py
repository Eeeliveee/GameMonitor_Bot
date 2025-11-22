import aiohttp
import json
import re


async def parse_epic_price(game_name):
    """
    Парсим Epic Games через GraphQL API или альтернативные источники
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    try:
        # Способ 1: Через GraphQL API Epic Store
        async with aiohttp.ClientSession(headers=headers) as session:
            # Ищем по названию через поиск
            search_url = f"https://store.epicgames.com/graphql"

            # GraphQL запрос для поиска игр
            graphql_query = {
                "query": """
                query searchStoreQuery($allowCountries: String, $category: String, $count: Int, $country: String!, $keywords: String, $locale: String, $sortBy: String, $sortDir: String, $start: Int, $tag: String) {
                    Catalog {
                        searchStore(allowCountries: $allowCountries, category: $category, count: $count, country: $country, keywords: $keywords, locale: $locale, sortBy: $sortBy, sortDir: $sortDir, start: $start, tag: $tag) {
                            elements {
                                title
                                price {
                                    totalPrice {
                                        discountPrice
                                        originalPrice
                                        currencyCode
                                    }
                                }
                                url
                            }
                        }
                    }
                }
                """,
                "variables": {
                    "country": "RU",
                    "locale": "ru",
                    "keywords": game_name,
                    "count": 5
                }
            }

            async with session.post(search_url, json=graphql_query) as response:
                if response.status == 200:
                    data = await response.json()

                    elements = data.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', [])

                    for element in elements:
                        if element['title'].lower() == game_name.lower():
                            price_info = element.get('price', {}).get('totalPrice', {})
                            price = price_info.get('discountPrice') or price_info.get('originalPrice')
                            if price:
                                return float(price)

        # Способ 2: Через альтернативный API
        async with aiohttp.ClientSession(headers=headers) as session:
            alt_url = f"https://store.epicgames.com/ru/p/"

            # Пробуем найти игру по slug (упрощенное название)
            slug = game_name.lower().replace(' ', '-').replace(':', '').replace("'", "")
            game_url = f"{alt_url}{slug}"

            async with session.get(game_url) as response:
                if response.status == 200:
                    html = await response.text()

                    # Ищем JSON данные в странице
                    json_pattern = r'window.__INITIAL_STATE__\s*=\s*({.*?});'
                    match = re.search(json_pattern, html)

                    if match:
                        json_data = json.loads(match.group(1))
                        # Здесь сложная структура Epic, нужно найти цену
                        # Упрощенный поиск
                        price_match = re.search(r'"totalPrice":\s*{\s*"discountPrice":\s*(\d+),', html)
                        if price_match:
                            return float(price_match.group(1))

        return None

    except Exception as e:
        print(f"Ошибка парсинга Epic Games {game_name}: {e}")
        return None