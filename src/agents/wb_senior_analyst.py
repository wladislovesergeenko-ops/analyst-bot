# src/agents/wb_senior_analyst.py

"""
Senior WB Analyst Agent v1.1

AI-агент уровня Senior Data Analyst для анализа данных Wildberries.
Отвечает на вопросы о марже, плане, воронке, рекламе.

Новое в v1.1:
- Memory — помнит контекст разговора
- Feedback — записывает ошибки для улучшения

Использование:
    python -m src.agents.wb_senior_analyst
"""

from src.graph import analyst_graph
from src.memory import ConversationMemory
from src.tools.feedback import record_full_feedback


class SeniorAnalyst:
    """
    Senior WB Analyst с памятью и feedback loop.
    """

    def __init__(self, session_id: str = None):
        self.memory = ConversationMemory(session_id)
        self.last_result = None

    def ask(self, question: str) -> str:
        """
        Задать вопрос агенту.

        Args:
            question: Вопрос на естественном языке

        Returns:
            Ответ агента
        """
        # Добавляем контекст из предыдущих вопросов
        context = self.memory.get_context()

        # Инициализируем state
        initial_state = {
            "question": question,
            "intent": "describe",
            "entities": {},
            "data_context": [],
            "insights": [],
            "recommendations": [],
            "response": "",
            "conversation_history": self.memory.history
        }

        # Запускаем граф
        result = analyst_graph.invoke(initial_state)

        # Сохраняем в память
        self.memory.add_exchange(
            question=question,
            response=result["response"],
            intent=result.get("intent"),
            tools_used=[item.get("tool") for item in result.get("data_context", [])]
        )

        self.last_result = result

        return result["response"]

    def report_error(self, comment: str, expected: str = None) -> str:
        """
        Сообщить об ошибке в последнем ответе.

        Args:
            comment: Что именно не так
            expected: Что должно было быть (опционально)

        Returns:
            Подтверждение записи
        """
        if not self.memory.last_question:
            return "Нет предыдущего вопроса для записи фидбека"

        # Определяем тип ошибки по ключевым словам
        comment_lower = comment.lower()
        if any(word in comment_lower for word in ["цифр", "данн", "числ", "сумм"]):
            feedback_type = "incorrect_data"
        elif any(word in comment_lower for word in ["рекоменд", "совет", "действ"]):
            feedback_type = "wrong_recommendation"
        elif any(word in comment_lower for word in ["расчёт", "формул", "считает"]):
            feedback_type = "wrong_calculation"
        elif any(word in comment_lower for word in ["нет", "не хватает", "добав"]):
            feedback_type = "missing_info"
        else:
            feedback_type = "other"

        result = record_full_feedback.invoke({
            "question": self.memory.last_question,
            "response": self.memory.last_response,
            "feedback_type": feedback_type,
            "user_comment": comment,
            "expected_answer": expected or "",
            "tools_used": self.memory.last_tools_used or []
        })

        return result

    def get_session_id(self) -> str:
        """Получить ID текущей сессии."""
        return self.memory.session_id


# Простая функция для обратной совместимости
def ask(question: str) -> str:
    """
    Задать вопрос Senior WB Analyst (без памяти).

    Args:
        question: Вопрос на естественном языке

    Returns:
        Ответ агента
    """
    initial_state = {
        "question": question,
        "intent": "describe",
        "entities": {},
        "data_context": [],
        "insights": [],
        "recommendations": [],
        "response": "",
        "conversation_history": []
    }

    result = analyst_graph.invoke(initial_state)
    return result["response"]


def interactive_session():
    """Интерактивная сессия с агентом (с памятью)."""

    analyst = SeniorAnalyst()

    print("=" * 60)
    print("Senior WB Analyst v1.1")
    print(f"Session ID: {analyst.get_session_id()}")
    print("=" * 60)
    print("Команды:")
    print("  exit/quit — выход")
    print("  /error <комментарий> — сообщить об ошибке в ответе")
    print("  /history — показать историю")
    print("=" * 60)

    while True:
        print()
        user_input = input("Вы: ").strip()

        if not user_input:
            continue

        # Команды
        if user_input.lower() in ["exit", "quit", "выход", "q"]:
            print("До свидания!")
            break

        if user_input.startswith("/error"):
            comment = user_input[6:].strip()
            if not comment:
                print("Укажите что не так. Пример: /error маржа должна быть 50к, а не 30к")
                continue
            print(analyst.report_error(comment))
            continue

        if user_input == "/history":
            if analyst.memory.history:
                print("\nИстория сессии:")
                for i, ex in enumerate(analyst.memory.history, 1):
                    print(f"\n{i}. Вопрос: {ex['question']}")
                    print(f"   Intent: {ex['intent']}")
            else:
                print("История пуста")
            continue

        # Обычный вопрос
        print()
        print("Анализирую...")
        print()

        try:
            response = analyst.ask(user_input)
            print("Аналитик:")
            print(response)
            print()
            print("(Если ответ неверный — напишите /error <что не так>)")
        except Exception as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    import sys

    # Если есть аргумент --test — запускаем тесты
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_questions = [
            "Какая маржа была вчера?",
            "Как выполняется план по марже?",
            "Почему упала маржа на прошлой неделе?",
            "Какие SKU нужно оптимизировать?",
            "Что делать чтобы выполнить план?",
        ]

        print("=" * 60)
        print("ТЕСТ Senior WB Analyst v1.1")
        print("=" * 60)

        analyst = SeniorAnalyst()

        for question in test_questions:
            print(f"\n{'='*60}")
            print(f"ВОПРОС: {question}")
            print("=" * 60)

            try:
                response = analyst.ask(question)
                print(response)
            except Exception as e:
                print(f"ОШИБКА: {e}")
                import traceback
                traceback.print_exc()
    else:
        # Интерактивный режим
        interactive_session()
