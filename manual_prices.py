# Ручная база цен в РУБЛЯХ
MANUAL_PRICES = {
    "ire: a prologue": {
        "steam": 710.0,
        "epic": 600.0
    },
    "cyberpunk 2077": {
        "steam": 1999.0,
        "epic": 1999.0
    },
    "the witcher 3: wild hunt": {
        "steam": 399.0,
        "epic": 399.0
    },
    "grand theft auto v": {
        "steam": 1499.0,
        "epic": 1299.0
    },
    "red dead redemption 2": {
        "steam": 2499.0,
        "epic": 2299.0
    },
    "elden ring": {
        "steam": 3499.0,
        "epic": 3499.0
    },
    "hogwarts legacy": {
        "steam": 2999.0,
        "epic": 2999.0
    }
}


async def get_manual_price(game_name):
    """Возвращает ручные цены если игра есть в базе"""
    # Пробуем точное совпадение
    if game_name.lower() in MANUAL_PRICES:
        return MANUAL_PRICES[game_name.lower()]

    # Пробуем частичное совпадение
    for key in MANUAL_PRICES:
        if key in game_name.lower() or game_name.lower() in key:
            print(f"🎯 Частичное совпадение: {key} -> {game_name}")
            return MANUAL_PRICES[key]

    return None