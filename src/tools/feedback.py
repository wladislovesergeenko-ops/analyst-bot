# src/tools/feedback.py

"""
Feedback Tool — запись обратной связи от пользователя.

Используется когда:
- Ответ агента неправильный
- Данные не соответствуют реальности
- Рекомендации некорректные
- Чего-то не хватает в ответе
"""

import json
from datetime import datetime
from langchain_core.tools import tool
from src.db.supabase import supabase


@tool
def record_feedback(
    feedback_type: str,
    user_comment: str,
    expected_answer: str = None
) -> str:
    """
    Записать обратную связь о некорректном ответе агента.

    Используй этот tool когда пользователь указывает на ошибку в ответе,
    говорит что данные неправильные или ожидал другой результат.

    Args:
        feedback_type: Тип проблемы. Допустимые значения:
            - incorrect_data: Данные неправильные (цифры не совпадают)
            - wrong_recommendation: Рекомендация некорректная
            - missing_info: Не хватает информации в ответе
            - wrong_calculation: Ошибка в расчётах
            - other: Другая проблема
        user_comment: Комментарий пользователя (что именно не так)
        expected_answer: Что должно было быть (если пользователь указал)

    Returns:
        Подтверждение записи фидбека
    """
    valid_types = ['incorrect_data', 'wrong_recommendation', 'missing_info',
                   'wrong_calculation', 'other']

    if feedback_type not in valid_types:
        feedback_type = 'other'

    try:
        data = {
            "feedback_type": feedback_type,
            "user_comment": user_comment,
            "expected_answer": expected_answer,
            "status": "new"
        }

        response = supabase.table("agent_feedback") \
            .insert(data) \
            .execute()

        return f"""✅ Фидбек записан. Спасибо!

Тип: {feedback_type}
Комментарий: {user_comment}
{f"Ожидаемый ответ: {expected_answer}" if expected_answer else ""}

Мы проанализируем эту ошибку и улучшим систему."""

    except Exception as e:
        return f"❌ Не удалось записать фидбек: {str(e)}"


@tool
def record_full_feedback(
    question: str,
    response: str,
    feedback_type: str,
    user_comment: str,
    expected_answer: str = None,
    tools_used: list = None
) -> str:
    """
    Записать полный фидбек с контекстом вопроса и ответа.

    Используется системой для записи детального фидбека.

    Args:
        question: Исходный вопрос пользователя
        response: Ответ агента который был неправильным
        feedback_type: Тип проблемы
        user_comment: Комментарий пользователя
        expected_answer: Ожидаемый правильный ответ
        tools_used: Список tools которые использовались

    Returns:
        Подтверждение записи
    """
    valid_types = ['incorrect_data', 'wrong_recommendation', 'missing_info',
                   'wrong_calculation', 'other']

    if feedback_type not in valid_types:
        feedback_type = 'other'

    try:
        data = {
            "question": question,
            "response": response[:5000] if response else None,  # Ограничиваем размер
            "feedback_type": feedback_type,
            "user_comment": user_comment,
            "expected_answer": expected_answer,
            "tools_used": json.dumps(tools_used) if tools_used else None,
            "status": "new"
        }

        response = supabase.table("agent_feedback") \
            .insert(data) \
            .execute()

        return "✅ Полный фидбек записан"

    except Exception as e:
        return f"❌ Ошибка записи: {str(e)}"


@tool
def get_feedback_stats() -> str:
    """
    Получить статистику по фидбеку (для анализа).

    Returns:
        Статистика: сколько фидбеков, по типам, статусам
    """
    try:
        response = supabase.table("agent_feedback") \
            .select("feedback_type, status") \
            .execute()

        if not response.data:
            return "Фидбеков пока нет"

        total = len(response.data)

        # По типам
        by_type = {}
        for row in response.data:
            t = row['feedback_type'] or 'other'
            by_type[t] = by_type.get(t, 0) + 1

        # По статусам
        by_status = {}
        for row in response.data:
            s = row['status'] or 'new'
            by_status[s] = by_status.get(s, 0) + 1

        result = f"""Статистика фидбека:

Всего записей: {total}

По типам:
"""
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            result += f"  • {t}: {count}\n"

        result += "\nПо статусам:\n"
        for s, count in sorted(by_status.items(), key=lambda x: -x[1]):
            result += f"  • {s}: {count}\n"

        return result

    except Exception as e:
        return f"Ошибка получения статистики: {str(e)}"


if __name__ == "__main__":
    print("=== Тест записи фидбека ===")
    print(record_feedback.invoke({
        "feedback_type": "incorrect_data",
        "user_comment": "Маржа показана 30к, а должна быть 50к",
        "expected_answer": "Маржа за вчера: 50,000 ₽"
    }))

    print("\n=== Статистика ===")
    print(get_feedback_stats.invoke({}))
