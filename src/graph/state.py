# src/graph/state.py

from typing import TypedDict, Literal, Annotated
from operator import add


class AnalystState(TypedDict):
    """State для Senior WB Analyst агента."""

    # Input
    question: str

    # Intent classification
    intent: Literal["describe", "diagnose", "prescribe", "clarify"]
    entities: dict  # {skus: [...], date_range: {...}, metrics: [...]}

    # Analysis results
    data_context: Annotated[list[dict], add]  # Результаты tools (аккумулируются)
    insights: Annotated[list[str], add]  # Найденные инсайты
    recommendations: list[dict]  # Приоритизированные рекомендации

    # Output
    response: str

    # Memory (для будущего)
    conversation_history: list[dict]
