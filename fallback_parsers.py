import aiohttp
import re


async def parse_epic_via_gg_deals(game_name):
    """Парсим через GG.deals как резервный вариант"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            search_url = f"https://gg.deals/games/?title={game_name}"
            async with session.get(search_url) as response:
                html = await response.text()

                # Ищем Epic Games цену в HTML
                epic_pattern = r'Epic Games[^>]*>[\s\S]*?(\d+[,.]\d+)\s*₽'
                match = re.search(epic_pattern, html)
                if match:
                    price = match.group(1).replace(',', '.')
                    return float(price)

        return None
    except Exception as e:
        print(f"Ошибка парсинга GG.deals {game_name}: {e}")
        return None