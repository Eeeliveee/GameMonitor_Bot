import aiohttp
import json


async def parse_gog_price(game_name):
    """
    Парсим GOG через их API
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # GOG API поиск
            search_url = f"https://embed.gog.com/games/ajax/filtered?mediaType=game&search={game_name}"

            async with session.get(search_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()

                    products = data.get('products', [])
                    for product in products:
                        if product['title'].lower() == game_name.lower():
                            price = product.get('price', {}).get('finalAmount')
                            if price:
                                return float(price)

        return None

    except Exception as e:
        print(f"Ошибка парсинга GOG {game_name}: {e}")
        return None