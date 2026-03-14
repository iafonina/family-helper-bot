"""
Логирование обращений к боту.
Сохраняет все диалоги в JSONL-файл для анализа.
"""
import json
import os
from datetime import datetime
from config import LOG_FILE


def ensure_log_dir():
    """Создаёт директорию для логов, если она не существует."""
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)


def log_conversation(
    user_id: int,
    username: str | None,
    first_name: str | None,
    user_message: str,
    bot_response: str,
    topic: str = "general",
):
    """
    Записывает обращение в лог-файл.

    Args:
        user_id: Telegram ID пользователя
        username: @username в Telegram
        first_name: Имя пользователя
        user_message: Текст вопроса
        bot_response: Ответ бота
        topic: Категория вопроса
    """
    ensure_log_dir()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "user_message": user_message,
        "bot_response": bot_response,
        "topic": topic,
        "response_length": len(bot_response),
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
