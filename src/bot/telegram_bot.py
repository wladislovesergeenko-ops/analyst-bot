# src/bot/telegram_bot.py

"""
Telegram Bot для Senior WB Analyst.

Позволяет общаться с аналитиком через Telegram.

Запуск:
    python -m src.bot.telegram_bot

Команды:
    /start - Начать работу
    /help - Справка по командам
    /error <комментарий> - Сообщить об ошибке в ответе
    /history - Показать историю вопросов
    /newsession - Начать новую сессию
"""

import os
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from dotenv import load_dotenv
load_dotenv()

from src.agents.wb_senior_analyst import SeniorAnalyst

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище сессий пользователей
user_sessions: dict[int, SeniorAnalyst] = {}


def get_analyst(user_id: int) -> SeniorAnalyst:
    """Получить или создать аналитика для пользователя."""
    if user_id not in user_sessions:
        user_sessions[user_id] = SeniorAnalyst(session_id=f"tg_{user_id}")
    return user_sessions[user_id]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    analyst = get_analyst(user.id)

    welcome_message = f"""👋 Привет, {user.first_name}!

Я **Senior WB Analyst** — AI-аналитик для Wildberries.

Могу помочь с:
• 📊 Анализ маржи и прибыльности
• 📈 Выполнение плана продаж
• 🔍 Диагностика проблем ("почему упала маржа?")
• 💡 Рекомендации по оптимизации

**Просто напиши вопрос**, например:
- "Какая маржа была вчера?"
- "Как выполняется план по марже?"
- "Какие SKU нужно оптимизировать?"

📌 Команды:
/help - Справка
/error - Сообщить об ошибке в ответе
/history - История вопросов
/newsession - Новая сессия

Session ID: `{analyst.get_session_id()}`
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    help_text = """📚 **Справка по командам**

**Вопросы на естественном языке:**
Просто напиши вопрос, например:
• "Какая маржа была вчера?"
• "Топ-5 прибыльных SKU"
• "Почему упала маржа на прошлой неделе?"
• "Что делать чтобы выполнить план?"

**Команды:**
/start - Приветствие и инструкции
/help - Эта справка
/error <текст> - Сообщить об ошибке в последнем ответе
/history - Показать историю вопросов в сессии
/newsession - Начать новую сессию (сбросить контекст)

**Примеры вопросов:**
📊 Описательные: "сколько заказов вчера?", "какая выручка?"
🔍 Диагностика: "почему упала маржа?", "что случилось с Омега-3?"
💡 Рекомендации: "что оптимизировать?", "как выполнить план?"
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def error_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /error."""
    user_id = update.effective_user.id
    analyst = get_analyst(user_id)

    # Получаем комментарий после команды
    comment = ' '.join(context.args) if context.args else None

    if not comment:
        await update.message.reply_text(
            "❓ Укажи что не так в ответе.\n\n"
            "Пример: `/error маржа должна быть 50к, а не 30к`",
            parse_mode='Markdown'
        )
        return

    result = analyst.report_error(comment)
    await update.message.reply_text(f"✅ {result}")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /history."""
    user_id = update.effective_user.id
    analyst = get_analyst(user_id)

    if not analyst.memory.history:
        await update.message.reply_text("📭 История пуста. Задай первый вопрос!")
        return

    history_text = "📜 **История сессии:**\n\n"
    for i, ex in enumerate(analyst.memory.history[-10:], 1):  # Последние 10
        question = ex['question'][:50] + "..." if len(ex['question']) > 50 else ex['question']
        history_text += f"{i}. {question}\n"
        history_text += f"   _Intent: {ex['intent']}_\n\n"

    await update.message.reply_text(history_text, parse_mode='Markdown')


async def newsession_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /newsession."""
    user_id = update.effective_user.id

    # Создаём нового аналитика
    user_sessions[user_id] = SeniorAnalyst(session_id=f"tg_{user_id}")
    analyst = user_sessions[user_id]

    await update.message.reply_text(
        f"🔄 Новая сессия начата!\n\n"
        f"Session ID: `{analyst.get_session_id()}`",
        parse_mode='Markdown'
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (вопросов)."""
    user_id = update.effective_user.id
    question = update.message.text

    # Показываем что бот печатает
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )

    analyst = get_analyst(user_id)

    try:
        # Получаем ответ от аналитика
        response = analyst.ask(question)

        # Telegram имеет лимит 4096 символов
        if len(response) > 4000:
            # Разбиваем на части
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            await update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка при обработке вопроса.\n\n"
            f"Попробуй переформулировать или напиши /newsession для новой сессии."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Запуск бота."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        print("\nДобавь токен в .env файл:")
        print("TELEGRAM_BOT_TOKEN=твой_токен_от_botfather")
        return

    # Очищаем токен от возможных пробелов и спецсимволов
    token = token.strip()

    print("🚀 Запуск Telegram бота...")
    print("Нажми Ctrl+C для остановки")

    # Создаём приложение
    app = Application.builder().token(token).build()

    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("error", error_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("newsession", newsession_command))

    # Обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Обработчик ошибок
    app.add_error_handler(error_handler)

    # Запускаем бота
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
