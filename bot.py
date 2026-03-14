"""
Семейный Помощник — Telegram-бот на базе Google Gemini API.
Помогает людям 50+ с бытовыми, финансовыми, юридическими,
медицинскими и автомобильными вопросами.
"""
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_HISTORY_LENGTH,
    ALLOWED_USERS,
    MAX_TOKENS,
)
from system_prompt import SYSTEM_PROMPT
from logger import log_conversation

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Инициализация клиента Google Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Множество разрешённых пользователей
allowed_user_ids: set[int] = set()
if ALLOWED_USERS:
    allowed_user_ids = {
        int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip()
    }


# ─── Health Check сервер для Koyeb ──────────────────────────────────


class HealthHandler(BaseHTTPRequestHandler):
    """Простой HTTP-обработчик для health check."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # Не засоряем логи health check запросами


def start_health_server():
    """Запускает HTTP-сервер для health check на порту 8000."""
    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
    server.serve_forever()


# ─── Логика бота ─────────────────────────────────────────────────────


def is_user_allowed(user_id: int) -> bool:
    """Проверяет, разрешён ли пользователю доступ к боту."""
    if not allowed_user_ids:
        return True
    return user_id in allowed_user_ids


def get_chat_history(context: ContextTypes.DEFAULT_TYPE) -> list[dict]:
    """Получает историю диалога из контекста пользователя."""
    if "history" not in context.user_data:
        context.user_data["history"] = []
    return context.user_data["history"]


def add_to_history(
    context: ContextTypes.DEFAULT_TYPE, role: str, content: str
):
    """Добавляет сообщение в историю диалога с ограничением длины."""
    history = get_chat_history(context)
    history.append({"role": role, "content": content})

    if len(history) > MAX_HISTORY_LENGTH:
        context.user_data["history"] = history[-MAX_HISTORY_LENGTH:]


def build_gemini_contents(history: list[dict]) -> list[types.Content]:
    """
    Преобразует историю диалога в формат Gemini API.
    Gemini использует роли 'user' и 'model' (не 'assistant').
    """
    contents = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])],
            )
        )
    return contents


async def get_gemini_response(
    user_message: str, context: ContextTypes.DEFAULT_TYPE
) -> str:
    """
    Отправляет запрос к Google Gemini API и возвращает ответ.
    """
    add_to_history(context, "user", user_message)
    history = get_chat_history(context)

    contents = build_gemini_contents(history)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=MAX_TOKENS,
                temperature=0.7,
            ),
        )

        assistant_message = response.text

        if not assistant_message:
            assistant_message = (
                "Извините, не удалось сформировать ответ. "
                "Попробуйте переформулировать вопрос."
            )

        add_to_history(context, "assistant", assistant_message)

        if response.usage_metadata:
            logger.info(
                f"Токены: вход={response.usage_metadata.prompt_token_count}, "
                f"выход={response.usage_metadata.candidates_token_count}"
            )

        return assistant_message

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка Gemini API: {error_msg}")

        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return (
                "Извините, сейчас слишком много обращений. "
                "Пожалуйста, подождите пару минут и попробуйте снова."
            )
        elif "400" in error_msg or "INVALID" in error_msg:
            context.user_data["history"] = [
                {"role": "user", "content": user_message}
            ]
            return (
                "Произошла ошибка при обработке запроса. "
                "Я начал новый разговор — попробуйте задать вопрос ещё раз."
            )
        elif "403" in error_msg or "API_KEY" in error_msg:
            return (
                "Произошла ошибка авторизации. "
                "Попросите Ирину проверить настройки бота."
            )
        else:
            return (
                "Что-то пошло не так. Попробуйте задать вопрос ещё раз. "
                "Если проблема повторяется — напишите Ирине."
            )


# ─── Обработчики команд ─────────────────────────────────────────────


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик команды /start."""
    user = update.effective_user

    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "Извините, у вас нет доступа к этому боту. "
            "Обратитесь к Ирине для получения доступа."
        )
        return

    welcome_text = (
        f"Здравствуйте, {user.first_name}! 👋\n\n"
        "Я — *Семейный Помощник*. Я помогу вам разобраться "
        "с разными вопросами:\n\n"
        "🏠 *Бытовые* — ЖКХ, Госуслуги, мастера\n"
        "💰 *Финансовые* — пенсии, льготы, банки\n"
        "⚖️ *Юридические* — документы, права, жалобы\n"
        "🏥 *Медицинские* — запись к врачу, лекарства\n"
        "🚗 *Автомобильные* — обслуживание, страховка\n\n"
        "Просто напишите свой вопрос обычным сообщением, "
        "и я постараюсь помочь!\n\n"
        "Команды:\n"
        "/help — что я умею\n"
        "/new — начать новый разговор\n"
    )

    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик команды /help."""
    if not is_user_allowed(update.effective_user.id):
        return

    help_text = (
        "*Как мной пользоваться:*\n\n"
        "1. Просто напишите свой вопрос — я отвечу\n"
        "2. Можно задавать уточняющие вопросы — я помню контекст разговора\n"
        "3. Если хотите начать новую тему — нажмите /new\n\n"
        "*Примеры вопросов:*\n\n"
        "• «Как передать показания счётчиков воды?»\n"
        "• «Какие льготы положены пенсионерам в Москве?»\n"
        "• «Как вернуть товар в магазин?»\n"
        "• «Когда нужно менять масло в машине?»\n"
        "• «Болит голова и температура 37.5 — что это может быть?»\n\n"
        "⚠️ *Важно:* Я не заменяю врача или юриста. "
        "По серьёзным вопросам всегда рекомендую обратиться к специалисту."
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def new_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик команды /new — сброс истории диалога."""
    if not is_user_allowed(update.effective_user.id):
        return

    context.user_data["history"] = []
    await update.message.reply_text(
        "Начинаем новый разговор! Задавайте ваш вопрос. 😊"
    )


# ─── Обработчик сообщений ───────────────────────────────────────────


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик текстовых сообщений."""
    user = update.effective_user

    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "Извините, у вас нет доступа к этому боту."
        )
        return

    user_message = update.message.text

    if not user_message or not user_message.strip():
        return

    await update.message.chat.send_action("typing")

    bot_response = await get_gemini_response(user_message, context)

    log_conversation(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        user_message=user_message,
        bot_response=bot_response,
    )

    if len(bot_response) <= 4096:
        try:
            await update.message.reply_text(
                bot_response, parse_mode="Markdown"
            )
        except Exception:
            await update.message.reply_text(bot_response)
    else:
        chunks = split_message(bot_response, 4096)
        for chunk in chunks:
            try:
                await update.message.reply_text(
                    chunk, parse_mode="Markdown"
                )
            except Exception:
                await update.message.reply_text(chunk)


def split_message(text: str, max_length: int = 4096) -> list[str]:
    """Разбивает длинное сообщение на части по абзацам."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for paragraph in text.split("\n\n"):
        if len(current_chunk) + len(paragraph) + 2 <= max_length:
            if current_chunk:
                current_chunk += "\n\n"
            current_chunk += paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(paragraph) > max_length:
                lines = paragraph.split("\n")
                current_chunk = ""
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= max_length:
                        if current_chunk:
                            current_chunk += "\n"
                        current_chunk += line
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = line
            else:
                current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def handle_non_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик голосовых, фото и других нетекстовых сообщений."""
    if not is_user_allowed(update.effective_user.id):
        return

    await update.message.reply_text(
        "Пока я умею работать только с текстовыми сообщениями. "
        "Напишите свой вопрос текстом, пожалуйста. 🙂"
    )


# ─── Запуск бота ─────────────────────────────────────────────────────


def main():
    """Запуск бота."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "Не указан TELEGRAM_BOT_TOKEN. "
            "Установите переменную окружения TELEGRAM_BOT_TOKEN."
        )

    if not GEMINI_API_KEY:
        raise ValueError(
            "Не указан GEMINI_API_KEY. "
            "Установите переменную окружения GEMINI_API_KEY."
        )

    # Запускаем health check сервер в отдельном потоке
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    logger.info("Health check сервер запущен на порту 8000")

    # Создаём приложение бота
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.add_handler(
        MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_non_text)
    )

    logger.info("Бот запущен и готов к работе!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
