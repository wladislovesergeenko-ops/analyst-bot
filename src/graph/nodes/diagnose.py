# src/graph/nodes/diagnose.py

"""
Diagnose Node — анализ причин изменений.

Отвечает на вопросы "почему?" и выявляет факторы.
"""

from src.graph.state import AnalystState
from src.tools.wb_diagnostics import (
    compare_periods,
    analyze_margin_change,
    find_margin_anomalies,
    diagnose_sku
)


def diagnose(state: AnalystState) -> AnalystState:
    """
    Выполняет диагностический анализ.

    Вызывает diagnostic tools для выявления причин изменений.
    """
    question = state["question"].lower()
    entities = state.get("entities", {})
    data_context = state.get("data_context", [])
    insights = state.get("insights", [])

    # Извлекаем SKU если упоминается
    skus = entities.get("skus", [])

    # Определяем какие diagnostic tools вызвать

    # Если спрашивают про конкретный SKU
    if skus:
        for sku in skus[:3]:  # Максимум 3 SKU
            try:
                nmid = int(sku) if str(sku).isdigit() else None
                if nmid:
                    result = diagnose_sku.invoke({"nmid": nmid, "days": 7})
                    data_context.append({"tool": "diagnose_sku", "result": result})
            except Exception:
                pass

    # Если спрашивают "почему упало/изменилось"
    if any(word in question for word in ["почему", "причин", "что случил", "что произошл"]):
        result = analyze_margin_change.invoke({"days_back": 7})
        data_context.append({"tool": "analyze_margin_change", "result": result})

    # Сравнение периодов
    if any(word in question for word in ["сравн", "неделя", "период", "было"]):
        result = compare_periods.invoke({
            "period1_start": "2026-01-06",
            "period1_end": "2026-01-12",
            "period2_start": "2026-01-13",
            "period2_end": "2026-01-18"
        })
        data_context.append({"tool": "compare_periods", "result": result})

    # Поиск аномалий
    if any(word in question for word in ["аномал", "резк", "скачок", "провал", "выброс"]):
        result = find_margin_anomalies.invoke({"days": 7})
        data_context.append({"tool": "find_anomalies", "result": result})

    # Если ничего не выбрано — делаем общий анализ
    if not any(item['tool'].startswith(('analyze', 'compare', 'find_anomalies', 'diagnose_sku'))
               for item in data_context):
        result = analyze_margin_change.invoke({"days_back": 7})
        data_context.append({"tool": "analyze_margin_change", "result": result})

    return {
        **state,
        "data_context": data_context,
        "insights": insights
    }
