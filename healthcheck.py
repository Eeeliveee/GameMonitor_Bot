#!/usr/bin/env python3
import sqlite3
import os
import sys

from GameMonitor_Bot.database import DB_PATH


def healthcheck():
    """Проверка здоровья приложения для Docker"""
    try:
        # Проверяем доступность базы данных
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()

        # Проверяем наличие критических файлов
        required_files = ['main.py', 'database.py', 'requirements.txt']
        for file in required_files:
            if not os.path.exists(file):
                return False

        return True
    except Exception as e:
        print(f"Healthcheck failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    sys.exit(0 if healthcheck() else 1)