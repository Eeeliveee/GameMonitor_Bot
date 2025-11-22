from .steam_parser import parse_steam_price
from .smart_parsers import parse_epic_via_cheapshark
from .manual_prices import get_manual_price
import sys
import os

from .simple_currency import convert_usd_to_rub




async def parse_game_price(game_name, platform="all"):
    """Умный парсинг с конвертацией валют"""

    prices = {}

    # Сначала проверяем ручную базу
    manual_price = await get_manual_price(game_name)
    if manual_price:
        print(f"🎯 Использую ручные цены для {game_name}")
        return manual_price

    # Steam парсим напрямую (уже в рублях)
    if platform in ["all", "steam"]:
        steam_price = await parse_steam_price(game_name)
        if steam_price:
            prices["steam"] = steam_price
            print(f"✅ Steam: {game_name} - {steam_price} руб")

    # Epic через API с конвертацией
    if platform in ["all", "epic"]:
        api_prices = await parse_epic_via_cheapshark(game_name)
        if api_prices and api_prices.get('epic'):
            prices["epic"] = api_prices['epic']
            print(f"✅ Epic: {game_name} - {api_prices['epic']} руб")

    # Если Epic не нашли, но есть Steam цена
    if platform in ["all", "epic"] and "epic" not in prices and "steam" in prices:
        # Предполагаем что Epic на 10-15% дешевле Steam
        epic_estimated = prices["steam"] * 0.88  # -12%
        prices["epic"] = round(epic_estimated, 2)
        print(f"ℹ️ Epic (оценка): {game_name} - {prices['epic']} руб")

    return prices