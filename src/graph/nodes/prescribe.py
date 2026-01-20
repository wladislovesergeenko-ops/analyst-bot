# src/graph/nodes/prescribe.py

"""
Prescribe Node — генерация рекомендаций.

Отвечает на вопросы "что делать?" и формирует action plan.
"""

from src.graph.state import AnalystState
from src.tools.wb_recommendations import (
    get_optimization_candidates,
    get_scaling_candidates,
    get_plan_recommendations,
    get_actionable_insights
)


def prescribe(state: AnalystState) -> AnalystState:
    """
    Генерирует рекомендации на основе данных.

    Вызывает recommendation tools и формирует приоритизированный список действий.
    """
    question = state["question"].lower()
    data_context = state.get("data_context", [])
    recommendations = []

    # Определяем какие recommendation tools вызвать

    # Общий вопрос "что делать"
    if any(word in question for word in ["что делать", "как улучш", "рекоменд", "совет", "действ"]):
        result = get_actionable_insights.invoke({})
        data_context.append({"tool": "actionable_insights", "result": result})

    # Оптимизация
    if any(word in question for word in ["оптимиз", "снизить", "сэконом", "убыточ", "дрр"]):
        result = get_optimization_candidates.invoke({})
        data_context.append({"tool": "optimization_candidates", "result": result})

    # Масштабирование/рост
    if any(word in question for word in ["масштаб", "увелич", "рост", "больше", "скейл"]):
        result = get_scaling_candidates.invoke({})
        data_context.append({"tool": "scaling_candidates", "result": result})

    # План
    if any(word in question for word in ["план", "выполн", "kpi", "цел"]):
        result = get_plan_recommendations.invoke({})
        data_context.append({"tool": "plan_recommendations", "result": result})

    # Если ничего не выбрано — даём топ-5 действий
    if not any(item['tool'] in ['actionable_insights', 'optimization_candidates',
                                 'scaling_candidates', 'plan_recommendations']
               for item in data_context):
        result = get_actionable_insights.invoke({})
        data_context.append({"tool": "actionable_insights", "result": result})

    return {
        **state,
        "data_context": data_context,
        "recommendations": recommendations
    }
