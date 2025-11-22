import aiohttp
import re
from bs4 import BeautifulSoup


async def parse_steam_price(game_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    print(f"🔍 Steam парсер ищет: '{game_name}'")

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # Кодируем название для URL
            encoded_name = game_name.replace(' ', '%20')
            search_url = f"https://store.steampowered.com/search/?term={encoded_name}&cc=ru"

            async with session.get(search_url) as response:
                html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            results = soup.find_all('a', class_='search_result_row')

            if not results:
                print("❌ Steam: не найдено результатов")
                return None

            print(f"🎯 Steam нашел {len(results)} результатов")

            # Ищем наиболее релевантный результат
            for i, result in enumerate(results[:5]):  # Проверяем первые 5 результатов
                title_span = result.find('span', class_='title')
                found_title = title_span.text if title_span else "Неизвестно"

                # Проверяем релевантность
                search_lower = game_name.lower()
                found_lower = found_title.lower()

                # Разные уровни совпадения
                exact_match = search_lower == found_lower
                contains_match = search_lower in found_lower
                words_match = any(word in found_lower for word in search_lower.split())

                print(f"  {i + 1}. '{found_title}'")
                print(f"     Точное: {exact_match}, Содержит: {contains_match}, Слова: {words_match}")

                # Если нашли хорошее совпадение - берем эту игру
                if exact_match or contains_match or words_match:
                    print(f"✅ ВЗЯЛИ: '{found_title}'")

                    # Парсим цену
                    price_div = result.find('div', class_='discount_final_price')
                    if price_div:
                        price_text = price_div.text.strip()
                        price_match = re.search(r'[\d,.]+', price_text)
                        if price_match:
                            price = price_match.group().replace(',', '.').replace(' ', '')
                            final_price = float(price) if price else None
                            print(f"💰 Steam цена: {final_price} руб")
                            return final_price
                    else:
                        print("❌ Не удалось найти цену")
                        return None

            print("❌ Не найдено релевантных игр")
            return None

    except Exception as e:
        print(f"❌ Ошибка парсинга Steam {game_name}: {e}")
        return None