# src/graph/nodes/classify.py

import json
from langchain_openai import ChatOpenAI
from src.config import OPENAI_API_KEY
from src.graph.state import AnalystState
from src.prompts.senior_analyst import CLASSIFY_PROMPT


llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    api_key=OPENAI_API_KEY,
    temperature=0
)


def classify_intent(state: AnalystState) -> AnalystState:
    """
    Классифицирует вопрос пользователя и извлекает сущности.

    Intent types:
    - describe: запрос фактов, метрик, топов
    - diagnose: анализ причин
    - prescribe: запрос рекомендаций
    - clarify: вопрос непонятен
    """
    question = state["question"]

    prompt = CLASSIFY_PROMPT.format(question=question)

    response = llm.invoke(prompt)

    # Парсим JSON из ответа
    try:
        # Убираем markdown если есть
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        intent = result.get("intent", "describe")
        entities = result.get("entities", {})

    except (json.JSONDecodeError, IndexError):
        # Fallback - пытаемся определить intent по ключевым словам
        question_lower = question.lower()

        if any(word in question_lower for word in ["почему", "причин", "упал", "снизил", "что случил"]):
            intent = "diagnose"
        elif any(word in question_lower for word in ["что делать", "как улучш", "рекоменд", "оптимиз", "совет"]):
            intent = "prescribe"
        elif any(word in question_lower for word in ["какой", "сколько", "покажи", "топ", "план", "маржа", "выручка"]):
            intent = "describe"
        else:
            intent = "describe"

        entities = {
            "skus": [],
            "date_range": "yesterday",
            "metrics": []
        }

    return {
        **state,
        "intent": intent,
        "entities": entities
    }
