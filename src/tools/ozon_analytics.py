# src/tools/ozon_analytics.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase

TABLE_OZON_ANALYTICS = "ozon_analytics_data"


@tool
def get_ozon_daily_summary(date: str) -> str:
    """
    Получить сводку по всем SKU Ozon за конкретный день.

    Args:
        date: Дата в формате YYYY-MM-DD (например, '2026-01-15')

    Returns:
        Сводка: выручка, заказы, доставки, просмотры, конверсия
    """
    response = supabase.table(TABLE_OZON_ANALYTICS) \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных Ozon за {date}"

    df = pd.DataFrame(response.data)

    total_revenue = df["revenue"].sum()
    total_orders = df["ordered_units"].sum()
    total_delivered = df["delivered_units"].sum()
    total_views = df["hits_view"].sum()
    total_sessions = df["session_view"].sum()
    total_tocart = df["hits_tocart"].sum()

    # Конверсии
    cr_view_to_cart = (total_tocart / total_views * 100) if total_views > 0 else 0
    cr_session_to_order = (total_orders / total_sessions * 100) if total_sessions > 0 else 0

    summary = {
        "Дата": date,
        "SKU": len(df),
        "Выручка": f"{total_revenue:,.0f} ₽",
        "Заказов": int(total_orders),
        "Доставлено": int(total_delivered),
        "Просмотров": int(total_views),
        "Сессий": int(total_sessions),
        "Добавлений в корзину": int(total_tocart),
        "CR просмотр→корзина": f"{cr_view_to_cart:.2f}%",
        "CR сессия→заказ": f"{cr_session_to_order:.2f}%"
    }

    return "\n".join([f"{k}: {v}" for k, v in summary.items()])


@tool
def get_ozon_top_sku(date: str, metric: str = "revenue", n: int = 5) -> str:
    """
    Получить топ SKU Ozon по выбранной метрике.

    Args:
        date: Дата в формате YYYY-MM-DD
        metric: Метрика для сортировки (revenue, ordered_units, hits_view, session_view)
        n: Количество позиций в топе

    Returns:
        Топ-N SKU с показателями
    """
    ALLOWED_METRICS = ['revenue', 'ordered_units', 'hits_view', 'session_view', 'hits_tocart']

    if metric not in ALLOWED_METRICS:
        return f"Неизвестная метрика '{metric}'. Доступные: {', '.join(ALLOWED_METRICS)}"

    response = supabase.table(TABLE_OZON_ANALYTICS) \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных Ozon за {date}"

    df = pd.DataFrame(response.data)
    top = df.nlargest(n, metric)

    metric_names = {
        'revenue': 'выручке',
        'ordered_units': 'заказам',
        'hits_view': 'просмотрам',
        'session_view': 'сессиям',
        'hits_tocart': 'добавлениям в корзину'
    }

    result = f"Топ-{n} Ozon по {metric_names[metric]} за {date}:\n\n"
    for _, row in top.iterrows():
        title = row['product_name'][:40] if row['product_name'] else row['sku']
        sessions = row['session_view'] or 0
        orders = row['ordered_units'] or 0
        cr = (orders / sessions * 100) if sessions > 0 else 0

        result += f"• {title}...\n"
        result += f"  SKU: {row['sku']}\n"
        result += f"  Выручка: {row['revenue']:,.0f} ₽, Заказов: {orders}\n"
        result += f"  Просмотров: {row['hits_view']}, Сессий: {sessions}, CR: {cr:.1f}%\n\n"

    return result


@tool
def get_ozon_conversion_funnel(date: str) -> str:
    """
    Показать воронку конверсии Ozon за день: просмотры → корзина → заказы.

    Args:
        date: Дата в формате YYYY-MM-DD

    Returns:
        Воронка с конверсиями на каждом этапе
    """
    response = supabase.table(TABLE_OZON_ANALYTICS) \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных Ozon за {date}"

    df = pd.DataFrame(response.data)

    # Общие метрики
    views = df["hits_view"].sum()
    views_search = df["hits_view_search"].sum()
    views_pdp = df["hits_view_pdp"].sum()

    tocart = df["hits_tocart"].sum()
    tocart_search = df["hits_tocart_search"].sum()
    tocart_pdp = df["hits_tocart_pdp"].sum()

    orders = df["ordered_units"].sum()
    delivered = df["delivered_units"].sum()

    # Конверсии
    cr_view_to_cart = (tocart / views * 100) if views > 0 else 0
    cr_cart_to_order = (orders / tocart * 100) if tocart > 0 else 0
    cr_order_to_delivery = (delivered / orders * 100) if orders > 0 else 0
    cr_total = (orders / views * 100) if views > 0 else 0

    result = f"""Воронка конверсии Ozon за {date}:

📊 ПРОСМОТРЫ: {views:,}
   └── Из поиска: {views_search:,}
   └── Карточка товара: {views_pdp:,}

   ↓ CR {cr_view_to_cart:.2f}%

🛒 КОРЗИНА: {tocart:,}
   └── Из поиска: {tocart_search:,}
   └── Из карточки: {tocart_pdp:,}

   ↓ CR {cr_cart_to_order:.2f}%

📦 ЗАКАЗЫ: {orders:,}

   ↓ CR {cr_order_to_delivery:.1f}%

✅ ДОСТАВЛЕНО: {delivered:,}

Общая конверсия (просмотр→заказ): {cr_total:.2f}%
"""

    return result


@tool
def get_ozon_low_conversion_sku(date: str, min_views: int = 100, max_cr: float = 1.0) -> str:
    """
    Найти SKU с низкой конверсией (много просмотров, мало заказов).

    Args:
        date: Дата в формате YYYY-MM-DD
        min_views: Минимум просмотров для анализа (по умолчанию 100)
        max_cr: Максимальный CR для попадания в список (по умолчанию 1%)

    Returns:
        Список SKU с низкой конверсией — кандидаты на оптимизацию карточки
    """
    response = supabase.table(TABLE_OZON_ANALYTICS) \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных Ozon за {date}"

    df = pd.DataFrame(response.data)

    # Фильтруем по минимуму просмотров
    df = df[df["hits_view"] >= min_views]

    if df.empty:
        return f"Нет SKU с просмотрами >= {min_views} за {date}"

    # Считаем CR
    df["cr"] = df.apply(
        lambda row: (row["ordered_units"] / row["session_view"] * 100)
        if row["session_view"] > 0 else 0,
        axis=1
    )

    # Фильтруем по низкому CR
    low_cr = df[df["cr"] < max_cr].sort_values("hits_view", ascending=False)

    if low_cr.empty:
        return f"Нет SKU с CR < {max_cr}% за {date}"

    result = f"SKU Ozon с низкой конверсией за {date}:\n"
    result += f"(просмотров >= {min_views}, CR < {max_cr}%)\n\n"

    for _, row in low_cr.head(10).iterrows():
        title = row['product_name'][:35] if row['product_name'] else row['sku']

        result += f"• {title}...\n"
        result += f"  SKU: {row['sku']}\n"
        result += f"  Просмотров: {row['hits_view']:,}, Сессий: {row['session_view']:,}\n"
        result += f"  Заказов: {row['ordered_units']}, CR: {row['cr']:.2f}%\n"
        result += f"  Позиция в категории: {row['position_category']:.0f}\n\n"

    return result


if __name__ == "__main__":
    print("=== Сводка Ozon за день ===")
    print(get_ozon_daily_summary.invoke({"date": "2026-01-15"}))

    print("\n=== Топ-5 по выручке ===")
    print(get_ozon_top_sku.invoke({"date": "2026-01-15", "metric": "revenue", "n": 5}))

    print("\n=== Воронка конверсии ===")
    print(get_ozon_conversion_funnel.invoke({"date": "2026-01-15"}))

    print("\n=== SKU с низкой конверсией ===")
    print(get_ozon_low_conversion_sku.invoke({"date": "2026-01-15", "min_views": 50, "max_cr": 2.0}))
