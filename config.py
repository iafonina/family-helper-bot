"""
Конфигурация бота.
Все чувствительные данные берутся из переменных окружения.
"""
import os

# Telegram Bot Token (получаем через @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Google Gemini API Key (получаем на aistudio.google.com/apikey)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Модель Gemini (2.5 Flash — быстрая и бесплатная)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Максимальная длина контекста (количество сообщений в истории диалога)
MAX_HISTORY_LENGTH = int(os.getenv("MAX_HISTORY_LENGTH", "20"))

# Путь к файлу логов обращений
LOG_FILE = os.getenv("LOG_FILE", "logs/conversations.jsonl")

# Список Telegram user_id, которым разрешён доступ (через запятую)
# Если пусто — доступ открыт для всех
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "")

# Максимальное количество токенов в ответе
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
