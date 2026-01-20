# src/graph/nodes/describe.py

from datetime import datetime, timedelta
from src.graph.state import AnalystState

# Import tools
from src.tools.wb_margin import (
    get_margin_summary,
    get_margin_trend,
    get_top_margin_sku,
    get_bottom_margin_sku
)
from src.tools.wb_plan import (
    get_plan_fact_summary,
    get_underperforming_sku,
    get_plan_forecast
)
from src.tools.wb_funnel import (
    get_funnel_summary,
    get_stock_summary,
    get_low_conversion_sku
)
from src.tools.ads import (
    get_ads_summary,
    get_high_drr_campaigns,
    get_scalable_campaigns
)


def get_date_from_range(date_range: str) -> str:
    """Конвертирует date_range в конкретную дату."""
    today = datetime.now()

    if date_range == "today":
        return today.strftime("%Y-%m-%d")
    elif date_range == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_range == "last_week":
        return (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif isinstance(date_range, str) and "-" in date_range:
        # Уже конкретная дата
        return date_range
    else:
        # По умолчанию вчера
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")


def describe(state: AnalystState) -> AnalystState:
    """
    Собирает описательную аналитику на основе вопроса.

    Вызывает релевантные tools и добавляет результаты в data_context.
    """
    question = state["question"].lower()
    entities = state.get("entities", {})
    date_range = entities.get("date_range", "yesterday")
    date = get_date_from_range(date_range)

    data_context = []
    insights = []

    # Определяем какие tools вызвать на основе вопроса
    # Маржа
    if any(word in question for word in ["маржа", "прибыль", "финрез", "финансов"]):
        result = get_margin_summary.invoke({"date": date})
        data_context.append({"tool": "margin_summary", "result": result})

    # План/факт
    if any(word in question for word in ["план", "выполнен", "факт", "kpi"]):
        result = get_plan_fact_summary.invoke({})
        data_context.append({"tool": "plan_fact", "result": result})

        # Также добавляем прогноз
        forecast = get_plan_forecast.invoke({})
        data_context.append({"tool": "plan_forecast", "result": forecast})

    # Топ SKU
    if any(word in question for word in ["топ", "лучш", "лидер"]):
        result = get_top_margin_sku.invoke({"date": date, "n": 10})
        data_context.append({"tool": "top_margin_sku", "result": result})

    # Убыточные / худшие
    if any(word in question for word in ["убыточ", "худш", "минус", "отрицат", "проблем"]):
        result = get_bottom_margin_sku.invoke({"date": date, "n": 10})
        data_context.append({"tool": "bottom_margin_sku", "result": result})

    # Воронка
    if any(word in question for word in ["воронк", "конверс", "просмотр", "заказ", "выкуп"]):
        result = get_funnel_summary.invoke({"date": date})
        data_context.append({"tool": "funnel_summary", "result": result})

    # Остатки
    if any(word in question for word in ["остат", "сток", "склад", "наличи"]):
        result = get_stock_summary.invoke({"date": date})
        data_context.append({"tool": "stock_summary", "result": result})

    # Реклама
    if any(word in question for word in ["реклам", "drr", "дрр", "кампани", "ставк"]):
        result = get_ads_summary.invoke({"date": date})
        data_context.append({"tool": "ads_summary", "result": result})

        # Проблемные кампании
        high_drr = get_high_drr_campaigns.invoke({"date": date, "threshold": 15})
        data_context.append({"tool": "high_drr_campaigns", "result": high_drr})

    # Тренд
    if any(word in question for word in ["динамик", "тренд", "неделя", "дней", "измен"]):
        result = get_margin_trend.invoke({"days": 7})
        data_context.append({"tool": "margin_trend", "result": result})

    # Отстающие от плана
    if any(word in question for word in ["отстающ", "отставан", "недовыполн"]):
        result = get_underperforming_sku.invoke({"threshold": 80})
        data_context.append({"tool": "underperforming_sku", "result": result})

    # Если ничего не выбрано — даём общую сводку
    if not data_context:
        # Общая сводка: маржа + план + реклама
        margin = get_margin_summary.invoke({"date": date})
        data_context.append({"tool": "margin_summary", "result": margin})

        plan = get_plan_fact_summary.invoke({})
        data_context.append({"tool": "plan_fact", "result": plan})

    return {
        **state,
        "data_context": data_context,
        "insights": insights
    }
