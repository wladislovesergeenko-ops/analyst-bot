# src/bot/telegram_bot.py

"""
Telegram Bot для Агента Анатолия — AI-аналитика маркетплейсов.

Позволяет общаться с аналитиком через Telegram.
Поддерживает WB и Ozon, личные и групповые чаты.

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
import random
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

# Паттерны приветствий
GREETINGS = [
    "привет", "здравствуй", "здорово", "хай", "hello", "hi",
    "добрый день", "доброе утро", "добрый вечер", "приветик", "хелло"
]

# Ответы на приветствия
GREETING_RESPONSES = [
    "Привет! 👋 Чем могу помочь сегодня?",
    "Здравствуй! 😊 Готов анализировать данные. Что посмотрим?",
    "Привет! 🤖 Какой вопрос по аналитике?",
    "Привет-привет! 👋 Что интересует?",
]

# Callback данные для быстрых кнопок
QUICK_ACTIONS = {
    "wb_scale": "Покажи топ-10 артикулов для масштабирования рекламы на WB",
    "wb_optimize": "Покажи топ-10 артикулов на оптимизацию рекламы на WB",
    "ozon_scale": "Покажи топ-10 SKU для масштабирования рекламы на Ozon",
    "ozon_optimize": "Покажи топ-10 SKU на оптимизацию рекламы на Ozon",
}

# Статусные сообщения для typing indicator
STATUS_MESSAGES = [
    "🔍 Анализирую данные...",
    "📊 Обрабатываю запрос...",
    "✍️ Формирую ответ...",
]

# TTL сессий (24 часа)
SESSION_TTL_HOURS = 24

# ============================================================================
# ХРАНИЛИЩЕ СЕССИЙ С TTL
# ============================================================================

# Сессии: user_id -> (analyst, last_activity)
user_sessions: dict[int, tuple[SeniorAnalyst, datetime]] = {}


def get_analyst(user_id: int) -> SeniorAnalyst:
    """Получить или создать аналитика для пользователя."""
    now = datetime.now()

    if user_id in user_sessions:
        analyst, last_activity = user_sessions[user_id]
        # Проверяем не устарела ли сессия
        if now - last_activity < timedelta(hours=SESSION_TTL_HOURS):
            # Обновляем timestamp
            user_sessions[user_id] = (analyst, now)
            return analyst

    # Создаём новую сессию
    analyst = SeniorAnalyst(session_id=f"tg_{user_id}")
    user_sessions[user_id] = (analyst, now)
    return analyst


def cleanup_old_sessions():
    """Очистить устаревшие сессии."""
    now = datetime.now()
    expired_users = []

    for user_id, (analyst, last_activity) in user_sessions.items():
        if now - last_activity > timedelta(hours=SESSION_TTL_HOURS):
            expired_users.append(user_id)

    for user_id in expired_users:
        del user_sessions[user_id]

    if expired_users:
        logger.info(f"Cleaned up {len(expired_users)} expired sessions")


async def periodic_cleanup(interval_seconds: int = 3600):
    """Периодическая очистка сессий (каждый час)."""
    while True:
        await asyncio.sleep(interval_seconds)
        cleanup_old_sessions()


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def is_greeting(text: str) -> bool:
    """Проверить, является ли сообщение приветствием."""
    text_lower = text.lower().strip()
    if len(text_lower) < 30:
        for pattern in GREETINGS:
            if pattern in text_lower:
                return True
    return False


def detect_marketplace(text: str) -> str:
    """Определить маркетплейс по тексту вопроса."""
    text_lower = text.lower()
    if any(word in text_lower for word in ["ozon", "озон"]):
        return "ozon"
    return "wb"


def get_quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру быстрых действий."""
    keyboard = [
        [
            InlineKeyboardButton("🚀 WB: Масштабирование", callback_data="wb_scale"),
            InlineKeyboardButton("⚙️ WB: Оптимизация", callback_data="wb_optimize"),
        ],
        [
            InlineKeyboardButton("🚀 Ozon: Масштабирование", callback_data="ozon_scale"),
            InlineKeyboardButton("⚙️ Ozon: Оптимизация", callback_data="ozon_optimize"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_typing_with_status(chat_id: int, bot, stop_event: asyncio.Event):
    """Фоновая задача: typing action + статусные сообщения."""
    status_message = None
    status_index = 0

    try:
        while not stop_event.is_set():
            # Отправляем typing action
            await bot.send_chat_action(chat_id=chat_id, action='typing')

            # Обновляем статус каждые 3 секунды
            if status_index < len(STATUS_MESSAGES):
                if status_message:
                    try:
                        await status_message.edit_text(STATUS_MESSAGES[status_index])
                    except Exception:
                        pass
                else:
                    status_message = await bot.send_message(
                        chat_id=chat_id,
                        text=STATUS_MESSAGES[status_index]
                    )
                status_index += 1

            # Ждём 3 секунды или пока не остановят
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3)
                break
            except asyncio.TimeoutError:
                pass
    finally:
        # Удаляем статусное сообщение
        if status_message:
            try:
                await status_message.delete()
            except Exception:
                pass


async def process_question(user_id: int, question: str, marketplace: str = "wb") -> str:
    """Асинхронно обработать вопрос через агента."""
    analyst = get_analyst(user_id)

    if marketplace == "ozon":
        # Для Ozon добавляем контекст в вопрос (используем WB агента пока)
        # TODO: интегрировать полноценный Ozon агент
        question_with_context = f"[Ozon] {question}"
        response = await asyncio.to_thread(analyst.ask, question_with_context)
    else:
        response = await asyncio.to_thread(analyst.ask, question)

    return response


# ============================================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    analyst = get_analyst(user.id)

    welcome_message = f"""Привет, {user.first_name}! 👋

Меня зовут **Агент Анатолий** 🤖 — твой персональный аналитик маркетплейсов.

Могу помочь с:
📊 Анализ продаж и маржи (WB + Ozon)
📈 Рекламные кампании
🔍 Диагностика проблем ("почему упала маржа?")
💡 Рекомендации по оптимизации

**Просто напиши вопрос** или нажми кнопку ниже! ⬇️

📌 Команды:
/help - Справка
/newsession - Новая сессия

_Session: `{analyst.get_session_id()}`_
"""
    await update.message.reply_text(
        welcome_message,
        parse_mode='Markdown',
        reply_markup=get_quick_actions_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    help_text = """📚 **Справка — Агент Анатолий**

**Вопросы на естественном языке:**
Просто напиши вопрос, например:
• "Какая маржа была вчера?"
• "Топ-5 прибыльных SKU на WB"
• "Почему упала маржа на Ozon?"
• "Что делать чтобы выполнить план?"

**Быстрые кнопки:**
🚀 Масштабирование — SKU с хорошими показателями для увеличения бюджета
⚙️ Оптимизация — SKU с высоким ДРР для снижения ставок

**Команды:**
/start - Приветствие и кнопки
/help - Эта справка
/error <текст> - Сообщить об ошибке в ответе
/history - История вопросов
/newsession - Новая сессия

**Групповой чат:**
Упомяни меня @bot или ответь на моё сообщение
"""
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=get_quick_actions_keyboard()
    )


async def error_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /error."""
    user_id = update.effective_user.id
    analyst = get_analyst(user_id)

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
    for i, ex in enumerate(analyst.memory.history[-10:], 1):
        question = ex['question'][:50] + "..." if len(ex['question']) > 50 else ex['question']
        history_text += f"{i}. {question}\n"
        history_text += f"   _Intent: {ex['intent']}_\n\n"

    await update.message.reply_text(history_text, parse_mode='Markdown')


async def newsession_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /newsession."""
    user_id = update.effective_user.id
    now = datetime.now()

    # Создаём нового аналитика
    analyst = SeniorAnalyst(session_id=f"tg_{user_id}")
    user_sessions[user_id] = (analyst, now)

    await update.message.reply_text(
        f"🔄 Новая сессия начата!\n\n"
        f"Session ID: `{analyst.get_session_id()}`",
        parse_mode='Markdown',
        reply_markup=get_quick_actions_keyboard()
    )


# ============================================================================
# ОБРАБОТЧИК СООБЩЕНИЙ
# ============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    text = message.text

    # Логируем входящее сообщение
    logger.info(f"Message | user={user.id} | chat={chat.type} | len={len(text)}")

    # === Групповой чат: фильтр по упоминанию ===
    if chat.type in ['group', 'supergroup']:
        bot_username = context.bot.username
        is_mentioned = bot_username and f'@{bot_username}' in text
        is_reply_to_bot = (
            message.reply_to_message and
            message.reply_to_message.from_user and
            message.reply_to_message.from_user.id == context.bot.id
        )

        if not is_mentioned and not is_reply_to_bot:
            return  # Игнорируем сообщение в группе без упоминания

        # Убираем упоминание из текста
        if bot_username:
            text = text.replace(f'@{bot_username}', '').strip()

    # === Проверяем приветствие ===
    if is_greeting(text):
        response = random.choice(GREETING_RESPONSES)
        await message.reply_text(
            response,
            reply_markup=get_quick_actions_keyboard()
        )
        return

    # === Основная обработка вопроса ===
    chat_id = chat.id
    start_time = time.time()

    # Запускаем typing indicator в фоне
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(
        send_typing_with_status(chat_id, context.bot, stop_event)
    )

    try:
        # Определяем маркетплейс
        marketplace = detect_marketplace(text)

        # Получаем ответ от агента (асинхронно)
        response = await process_question(user.id, text, marketplace)

        elapsed = time.time() - start_time
        logger.info(f"Response | user={user.id} | time={elapsed:.2f}s | len={len(response)}")

        # Отправляем ответ
        if len(response) > 4000:
            # Разбиваем на части
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Последняя часть — с кнопками
                    await message.reply_text(
                        part,
                        parse_mode='Markdown',
                        reply_markup=get_quick_actions_keyboard()
                    )
                else:
                    await message.reply_text(part, parse_mode='Markdown')
        else:
            await message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=get_quick_actions_keyboard()
            )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error | user={user.id} | time={elapsed:.2f}s | error={e}", exc_info=True)
        await message.reply_text(
            "❌ Произошла ошибка при обработке вопроса.\n\n"
            "Попробуй переформулировать или напиши /newsession для новой сессии."
        )
    finally:
        # Останавливаем typing indicator
        stop_event.set()
        await typing_task


# ============================================================================
# ОБРАБОТЧИК КНОПОК
# ============================================================================

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки."""
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие

    user = query.from_user
    callback_data = query.data
    chat_id = query.message.chat_id

    if callback_data not in QUICK_ACTIONS:
        return

    # Получаем вопрос из callback
    question = QUICK_ACTIONS[callback_data]
    marketplace = "ozon" if callback_data.startswith("ozon_") else "wb"

    logger.info(f"Button | user={user.id} | action={callback_data}")

    # Показываем статус
    await query.edit_message_text(
        text=f"🔍 Анализирую: _{question}_...",
        parse_mode='Markdown'
    )

    start_time = time.time()

    try:
        # Получаем ответ
        response = await process_question(user.id, question, marketplace)

        elapsed = time.time() - start_time
        logger.info(f"Button response | user={user.id} | time={elapsed:.2f}s")

        # Отправляем ответ новым сообщением
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=part,
                        parse_mode='Markdown',
                        reply_markup=get_quick_actions_keyboard()
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=part,
                        parse_mode='Markdown'
                    )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=response,
                parse_mode='Markdown',
                reply_markup=get_quick_actions_keyboard()
            )

        # Удаляем статусное сообщение
        try:
            await query.message.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Button error | user={user.id} | error={e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка. Попробуй ещё раз или напиши вопрос текстом.",
            reply_markup=get_quick_actions_keyboard()
        )


# ============================================================================
# ОБРАБОТЧИК ОШИБОК
# ============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок."""
    logger.error(f"Global error | update={update} | error={context.error}", exc_info=True)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Запуск бота."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        print("\nДобавь токен в .env файл:")
        print("TELEGRAM_BOT_TOKEN=твой_токен_от_botfather")
        return

    token = token.strip()

    print("🚀 Запуск Telegram бота (Агент Анатолий)...")
    print("Нажми Ctrl+C для остановки")

    # Создаём приложение
    app = Application.builder().token(token).build()

    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("error", error_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("newsession", newsession_command))

    # Обработчик inline кнопок
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Обработчик текстовых сообщений (личные + группы)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    # Обработчик ошибок
    app.add_error_handler(error_handler)

    # Запускаем периодическую очистку сессий
    async def post_init(application):
        asyncio.create_task(periodic_cleanup())

    app.post_init = post_init

    # Запускаем бота
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
