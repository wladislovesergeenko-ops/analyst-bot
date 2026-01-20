# src/tools/ozon_ads.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase

TABLE_OZON_ADS = "ozon_campaign_product_stats"


@tool
def get_ozon_ads_summary(date: str) -> str:
    """
    Получить общую сводку по рекламе Ozon за день.

    Args:
        date: Дата в формате YYYY-MM-DD

    Returns:
        Сводка: расход, заказы (с ассоциированными), выручка, ДРР
    """
    response = supabase.table(TABLE_OZON_ADS) \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных по рекламе Ozon за {date}"

    df = pd.DataFrame(response.data)

    total_cost = df["cost"].sum()
    total_orders = df["orders"].sum() + df["model_orders"].sum()
    total_revenue = df["revenue"].sum() + df["model_revenue"].sum()
    total_clicks = df["clicks"].sum()
    total_impressions = df["impressions"].sum()
    total_add_to_cart = df["add_to_cart"].sum()

    # Метрики
    drr = (total_cost / total_revenue * 100) if total_revenue > 0 else 0
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    cr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
    cpc = (total_cost / total_clicks) if total_clicks > 0 else 0

    # Количество уникальных кампаний
    campaigns = df["campaign_id"].nunique()

    summary = {
        "Дата": date,
        "Кампаний": campaigns,
        "SKU в рекламе": len(df),
        "Расход": f"{total_cost:,.0f} ₽",
        "Показов": f"{total_impressions:,}",
        "Кликов": f"{total_clicks:,}",
        "В корзину": f"{total_add_to_cart:,}",
        "Заказов (всего)": int(total_orders),
        "Выручка (всего)": f"{total_revenue:,.0f} ₽",
        "ДРР": f"{drr:.1f}%",
        "CTR": f"{ctr:.2f}%",
        "CR (клик→заказ)": f"{cr:.1f}%",
        "CPC": f"{cpc:.1f} ₽"
    }

    return "\n".join([f"{k}: {v}" for k, v in summary.items()])


@tool
def get_ozon_high_drr_campaigns(date: str, threshold: float = 15.0) -> str:
    """
    Найти товары в кампаниях Ozon с высоким ДРР, требующие оптимизации.

    Args:
        date: Дата в формате YYYY-MM-DD
        threshold: Порог ДРР в процентах (по умолчанию 15%)

    Returns:
        Список товаров с высоким ДРР
    """
    response = supabase.table(TABLE_OZON_ADS) \
        .select("*") \
        .eq("date", date) \
        .gt("drr", threshold) \
        .execute()

    if not response.data:
        return f"Товаров с ДРР > {threshold}% за {date} не найдено"

    df = pd.DataFrame(response.data)
    df = df.sort_values("cost", ascending=False)

    result = f"Товары Ozon с ДРР > {threshold}% за {date}:\n\n"
    for _, row in df.head(15).iterrows():
        title = row['product_name'][:35] if row['product_name'] else row['sku']
        total_orders = (row['orders'] or 0) + (row['model_orders'] or 0)
        total_revenue = (row['revenue'] or 0) + (row['model_revenue'] or 0)

        result += f"• {title}...\n"
        result += f"  Кампания: {row['campaign_id']}\n"
        result += f"  Расход: {row['cost']:,.0f} ₽, Выручка: {total_revenue:,.0f} ₽\n"
        result += f"  ДРР: {row['drr']:.1f}%, Заказов: {total_orders}\n"
        result += f"  CPC: {row['avg_cpc']:.1f} ₽, CTR: {row['ctr']:.2f}%\n\n"

    return result


@tool
def get_ozon_scalable_campaigns(date: str, max_drr: float = 15.0, min_cr: float = 5.0) -> str:
    """
    Найти товары в кампаниях Ozon для масштабирования (низкий ДРР, высокий CR).

    Args:
        date: Дата в формате YYYY-MM-DD
        max_drr: Максимальный ДРР для масштабирования (по умолчанию 15%)
        min_cr: Минимальный CR клик→заказ (по умолчанию 5%)

    Returns:
        Список товаров, которые можно масштабировать
    """
    response = supabase.table(TABLE_OZON_ADS) \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных по рекламе Ozon за {date}"

    df = pd.DataFrame(response.data)

    # Считаем CR
    df["cr"] = df.apply(
        lambda row: ((row["orders"] + row["model_orders"]) / row["clicks"] * 100)
        if row["clicks"] > 0 else 0,
        axis=1
    )

    # Фильтруем: низкий ДРР и высокий CR
    scalable = df[(df["drr"] > 0) & (df["drr"] < max_drr) & (df["cr"] >= min_cr)]

    if scalable.empty:
        return f"Товаров для масштабирования (ДРР < {max_drr}%, CR >= {min_cr}%) за {date} не найдено"

    scalable = scalable.sort_values("cr", ascending=False)

    result = f"Товары Ozon для масштабирования за {date}:\n"
    result += f"(ДРР < {max_drr}%, CR >= {min_cr}%)\n\n"

    for _, row in scalable.head(10).iterrows():
        title = row['product_name'][:35] if row['product_name'] else row['sku']
        total_orders = row['orders'] + row['model_orders']
        total_revenue = row['revenue'] + row['model_revenue']

        result += f"• {title}...\n"
        result += f"  Кампания: {row['campaign_id']}\n"
        result += f"  Заказов: {total_orders}, Выручка: {total_revenue:,.0f} ₽\n"
        result += f"  ДРР: {row['drr']:.1f}%, CR: {row['cr']:.1f}%\n"
        result += f"  CPC: {row['avg_cpc']:.1f} ₽ — можно повысить ставку\n\n"

    return result


@tool
def get_ozon_ads_trend(metric: str, days: int = 7) -> str:
    """
    Показать динамику метрики рекламы Ozon за N дней.

    Args:
        metric: Метрика для анализа. Доступные:
            - impressions (показы)
            - clicks (клики)
            - orders (заказы, включая ассоциированные)
            - cost (расход)
            - revenue (выручка, включая ассоциированную)
            - ctr (CTR %)
            - cr (конверсия клик→заказ %)
            - avg_cpc (средний CPC)
            - drr (ДРР %)
            - add_to_cart (добавления в корзину)
        days: Количество дней (по умолчанию 7)

    Returns:
        Динамика метрики по дням
    """
    ALLOWED_METRICS = {
        'impressions': 'Показы',
        'clicks': 'Клики',
        'orders': 'Заказы',
        'cost': 'Расход ₽',
        'revenue': 'Выручка ₽',
        'ctr': 'CTR %',
        'cr': 'CR %',
        'avg_cpc': 'CPC ₽',
        'drr': 'ДРР %',
        'add_to_cart': 'В корзину'
    }

    if metric not in ALLOWED_METRICS:
        return f"Неизвестная метрика '{metric}'. Доступные: {', '.join(ALLOWED_METRICS.keys())}"

    response = supabase.table(TABLE_OZON_ADS) \
        .select("*") \
        .order("date", desc=True) \
        .limit(5000) \
        .execute()

    if not response.data:
        return "Нет данных по рекламе Ozon"

    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])

    # Фильтруем по количеству дней
    max_date = df['date'].max()
    min_date = max_date - pd.Timedelta(days=days - 1)
    df = df[df['date'] >= min_date]

    # Для orders и revenue суммируем с model_*
    if metric == 'orders':
        df['orders'] = df['orders'] + df['model_orders']
    elif metric == 'revenue':
        df['revenue'] = df['revenue'] + df['model_revenue']

    # Агрегируем по дням
    if metric in ['ctr', 'cr', 'drr', 'avg_cpc']:
        daily = df.groupby('date')[metric].mean().round(2)
    else:
        daily = df.groupby('date')[metric].sum().round(0)

    daily = daily.sort_index()

    # Формируем ответ
    metric_name = ALLOWED_METRICS[metric]
    result = f"Динамика '{metric_name}' Ozon за {days} дней:\n\n"

    for date, value in daily.items():
        date_str = date.strftime("%d.%m")
        if metric in ['cost', 'revenue', 'avg_cpc']:
            result += f"{date_str}: {value:,.0f} ₽\n"
        elif metric in ['ctr', 'cr', 'drr']:
            result += f"{date_str}: {value:.1f}%\n"
        else:
            result += f"{date_str}: {value:,.0f}\n"

    # Считаем изменение
    if len(daily) >= 2:
        first_val = daily.iloc[0]
        last_val = daily.iloc[-1]
        if first_val > 0:
            change = ((last_val - first_val) / first_val) * 100
            trend = "📈" if change > 0 else "📉"
            result += f"\nИзменение: {trend} {change:+.1f}%"

    return result


@tool
def get_ozon_campaign_details(campaign_id: str, date: str) -> str:
    """
    Получить детальную статистику по конкретной кампании Ozon.

    Args:
        campaign_id: ID кампании
        date: Дата в формате YYYY-MM-DD

    Returns:
        Детальная статистика по всем товарам в кампании
    """
    response = supabase.table(TABLE_OZON_ADS) \
        .select("*") \
        .eq("campaign_id", campaign_id) \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных по кампании {campaign_id} за {date}"

    df = pd.DataFrame(response.data)

    # Общие метрики кампании
    total_cost = df["cost"].sum()
    total_orders = df["orders"].sum() + df["model_orders"].sum()
    total_revenue = df["revenue"].sum() + df["model_revenue"].sum()
    total_clicks = df["clicks"].sum()
    total_impressions = df["impressions"].sum()

    drr = (total_cost / total_revenue * 100) if total_revenue > 0 else 0
    cr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0

    result = f"""Кампания {campaign_id} за {date}:

📊 ОБЩИЕ ПОКАЗАТЕЛИ:
Расход: {total_cost:,.0f} ₽
Выручка: {total_revenue:,.0f} ₽
Заказов: {total_orders}
ДРР: {drr:.1f}%
CR: {cr:.1f}%
Показов: {total_impressions:,}
Кликов: {total_clicks:,}

📦 ТОВАРЫ В КАМПАНИИ ({len(df)}):\n\n"""

    df = df.sort_values("cost", ascending=False)

    for _, row in df.iterrows():
        title = row['product_name'][:30] if row['product_name'] else row['sku']
        orders = row['orders'] + row['model_orders']
        revenue = row['revenue'] + row['model_revenue']

        result += f"• {title}...\n"
        result += f"  Цена: {row['price']:,.0f} ₽\n"
        result += f"  Расход: {row['cost']:,.0f} ₽, Выручка: {revenue:,.0f} ₽\n"
        result += f"  Заказов: {orders}, ДРР: {row['drr']:.1f}%\n"
        result += f"  Показов: {row['impressions']:,}, Кликов: {row['clicks']}, CTR: {row['ctr']:.2f}%\n\n"

    return result


if __name__ == "__main__":
    print("=== Сводка по рекламе Ozon ===")
    print(get_ozon_ads_summary.invoke({"date": "2025-12-22"}))

    print("\n=== Товары с высоким ДРР ===")
    print(get_ozon_high_drr_campaigns.invoke({"date": "2025-12-22", "threshold": 15}))

    print("\n=== Товары для масштабирования ===")
    print(get_ozon_scalable_campaigns.invoke({"date": "2025-12-22"}))

    print("\n=== Тренд ДРР за 7 дней ===")
    print(get_ozon_ads_trend.invoke({"metric": "drr", "days": 7}))

    print("\n=== Детали кампании ===")
    print(get_ozon_campaign_details.invoke({"campaign_id": "18982499", "date": "2025-12-22"}))
