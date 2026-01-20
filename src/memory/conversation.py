# src/memory/conversation.py

"""
Conversation Memory — сохранение истории разговора.

Использует:
- MemorySaver для сессии (in-memory)
- Supabase для persistence между сессиями
"""

import json
from datetime import datetime
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver
from src.db.supabase import supabase


# In-memory checkpointer для текущей сессии
memory_saver = MemorySaver()


def save_conversation_to_db(
    session_id: str,
    question: str,
    response: str,
    intent: str,
    tools_used: list = None
) -> bool:
    """
    Сохранить обмен в Supabase для долгосрочной памяти.

    Args:
        session_id: ID сессии
        question: Вопрос пользователя
        response: Ответ агента
        intent: Определённый intent
        tools_used: Список использованных tools

    Returns:
        True если успешно
    """
    try:
        data = {
            "session_id": session_id,
            "question": question,
            "response": response[:10000] if response else None,
            "intent": intent,
            "tools_used": json.dumps(tools_used) if tools_used else None,
            "created_at": datetime.now().isoformat()
        }

        # Проверяем есть ли таблица (может не быть)
        # Если нет — просто пропускаем
        try:
            supabase.table("agent_conversations") \
                .insert(data) \
                .execute()
            return True
        except Exception:
            # Таблица не существует — OK, работаем без persistence
            return False

    except Exception as e:
        print(f"Warning: Could not save conversation: {e}")
        return False


def get_conversation_history(session_id: str, limit: int = 10) -> list:
    """
    Получить историю разговора из Supabase.

    Args:
        session_id: ID сессии
        limit: Максимум записей

    Returns:
        Список предыдущих обменов
    """
    try:
        response = supabase.table("agent_conversations") \
            .select("question, response, intent, created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        if response.data:
            # Возвращаем в хронологическом порядке
            return list(reversed(response.data))
        return []

    except Exception:
        return []


def format_history_for_context(history: list) -> str:
    """
    Форматирует историю для добавления в контекст.

    Args:
        history: Список предыдущих обменов

    Returns:
        Отформатированная строка с историей
    """
    if not history:
        return ""

    result = "Предыдущие вопросы в этой сессии:\n\n"

    for i, item in enumerate(history[-5:], 1):  # Последние 5
        result += f"{i}. Вопрос: {item['question']}\n"
        # Берём только первые 200 символов ответа
        short_response = item['response'][:200] + "..." if len(item['response']) > 200 else item['response']
        result += f"   Ответ: {short_response}\n\n"

    return result


class ConversationMemory:
    """
    Класс для управления памятью разговора.

    Хранит историю в рамках сессии и может сохранять в БД.
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.history = []
        self.last_question = None
        self.last_response = None
        self.last_tools_used = []

    def add_exchange(
        self,
        question: str,
        response: str,
        intent: str = None,
        tools_used: list = None
    ):
        """Добавить обмен в историю."""
        exchange = {
            "question": question,
            "response": response,
            "intent": intent,
            "tools_used": tools_used or [],
            "timestamp": datetime.now().isoformat()
        }

        self.history.append(exchange)
        self.last_question = question
        self.last_response = response
        self.last_tools_used = tools_used or []

        # Сохраняем в БД (если таблица есть)
        save_conversation_to_db(
            self.session_id,
            question,
            response,
            intent,
            tools_used
        )

    def get_context(self) -> str:
        """Получить контекст для следующего вопроса."""
        if not self.history:
            return ""

        return format_history_for_context(self.history)

    def get_last_exchange(self) -> Optional[dict]:
        """Получить последний обмен."""
        if self.history:
            return self.history[-1]
        return None

    def clear(self):
        """Очистить историю сессии."""
        self.history = []
        self.last_question = None
        self.last_response = None
        self.last_tools_used = []
