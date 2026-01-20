# src/graph/nodes/synthesize.py

from langchain_openai import ChatOpenAI
from src.config import OPENAI_API_KEY
from src.graph.state import AnalystState
from src.prompts.senior_analyst import SYSTEM_PROMPT, SYNTHESIZE_PROMPT


llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    api_key=OPENAI_API_KEY,
    temperature=0.3
)


def synthesize(state: AnalystState) -> AnalystState:
    """
    Синтезирует финальный ответ на основе собранных данных.
    """
    question = state["question"]
    data_context = state.get("data_context", [])
    insights = state.get("insights", [])
    recommendations = state.get("recommendations", [])

    # Форматируем данные для промпта
    data_str = ""
    for item in data_context:
        data_str += f"\n### {item['tool']}:\n{item['result']}\n"

    insights_str = "\n".join(insights) if insights else "Нет дополнительных инсайтов"
    recommendations_str = "\n".join([str(r) for r in recommendations]) if recommendations else "Нет рекомендаций"

    # Формируем промпт
    user_prompt = SYNTHESIZE_PROMPT.format(
        question=question,
        data_context=data_str,
        insights=insights_str,
        recommendations=recommendations_str
    )

    # Вызываем LLM
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = llm.invoke(messages)

    return {
        **state,
        "response": response.content
    }
