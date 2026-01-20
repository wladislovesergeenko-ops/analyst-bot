# src/tools/wb_margin.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase
from datetime import datetime, timedelta


@tool
def get_margin_summary(date: str) -> str:
    """
    Получить сводку по марже за конкретный день.

    Args:
        date: Дата в формате YYYY-MM-DD

    Returns:
        Сводка: общая маржа, выручка, расход на рекламу, количество SKU
    """
    response = supabase.table("wb_margin_daily") \
        .select("*") \
        .eq("date", date) \
        .execute()

    if not response.data:
        return f"Нет данных по марже за {date}"

    df = pd.DataFrame(response.data)

    total_margin = df["margin_profit_after_ads"].sum()
    total_revenue = df["revenue_total"].sum()
    total_ad_spend = df["ad_spend"].sum()
    total_orders = df["ordercount"].sum()
    avg_margin_percent = df["margin_percent_after_ads"].mean()
    sku_count = len(df)

    # Profitable vs unprofitable
    profitable = df[df["margin_profit_after_ads"] > 0]
    unprofitable = df[df["margin_profit_after_ads"] <= 0]

    summary = f"""Сводка по марже за {date}:

SKU в продаже: {sku_count}
Заказов: {int(total_orders):,}
Выручка: {total_revenue:,.0f} ₽
Расход на рекламу: {total_ad_spend:,.0f} ₽
Маржа (после рекламы): {total_margin:,.0f} ₽
Средняя маржинальность: {avg_margin_percent:.1f}%

Прибыльных SKU: {len(profitable)} (маржа: {profitable['margin_profit_after_ads'].sum():,.0f} ₽)
Убыточных SKU: {len(unprofitable)} (убыток: {unprofitable['margin_profit_after_ads'].sum():,.0f} ₽)"""

    return summary


@tool
def get_margin_trend(days: int = 7) -> str:
    """
    Показать динамику маржи за последние N дней.

    Args:
        days: Количество дней для анализа (по умолчанию 7)

    Returns:
        Динамика маржи по дням с изменением
    """
    response = supabase.table("wb_margin_daily") \
        .select("date, margin_profit_after_ads, revenue_total, ad_spend") \
        .order("date", desc=True) \
        .limit(days * 150) \
        .execute()

    if not response.data:
        return "Нет данных по марже"

    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])

    # Агрегация по дням
    daily = df.groupby('date').agg({
        'margin_profit_after_ads': 'sum',
        'revenue_total': 'sum',
        'ad_spend': 'sum'
    }).sort_index()

    # Берём последние N дней
    daily = daily.tail(days)

    result = f"Динамика маржи за {days} дней:\n\n"
    result += "| Дата | Маржа | Выручка | Реклама | Маржа % |\n"
    result += "|------|-------|---------|---------|----------|\n"

    for date, row in daily.iterrows():
        margin_pct = (row['margin_profit_after_ads'] / row['revenue_total'] * 100) if row['revenue_total'] > 0 else 0
        result += f"| {date.strftime('%d.%m')} | {row['margin_profit_after_ads']:,.0f} ₽ | {row['revenue_total']:,.0f} ₽ | {row['ad_spend']:,.0f} ₽ | {margin_pct:.1f}% |\n"

    # Изменение за период
    if len(daily) >= 2:
        first_margin = daily.iloc[0]['margin_profit_after_ads']
        last_margin = daily.iloc[-1]['margin_profit_after_ads']
        if first_margin > 0:
            change = ((last_margin - first_margin) / first_margin) * 100
            trend = "📈" if change > 0 else "📉"
            result += f"\nИзменение: {trend} {change:+.1f}%"

    return result


@tool
def get_top_margin_sku(date: str, n: int = 10) -> str:
    """
    Получить топ SKU по маржинальной прибыли.

    Args:
        date: Дата в формате YYYY-MM-DD
        n: Количество позиций в топе (по умолчанию 10)

    Returns:
        Топ-N SKU по марже
    """
    response = supabase.table("wb_margin_daily") \
        .select("*") \
        .eq("date", date) \
        .order("margin_profit_after_ads", desc=True) \
        .limit(n) \
        .execute()

    if not response.data:
        return f"Нет данных за {date}"

    result = f"Топ-{n} SKU по марже за {date}:\n\n"

    for i, row in enumerate(response.data, 1):
        title = row['title'][:35] if row['title'] else str(row['nmid'])
        margin = row['margin_profit_after_ads'] or 0
        margin_pct = row['margin_percent_after_ads'] or 0
        revenue = row['revenue_total'] or 0
        orders = row['ordercount'] or 0
        ad_spend = row['ad_spend'] or 0

        result += f"{i}. {title}...\n"
        result += f"   Маржа: {margin:,.0f} ₽ ({margin_pct:.1f}%)\n"
        result += f"   Выручка: {revenue:,.0f} ₽, Заказов: {orders}\n"
        result += f"   Реклама: {ad_spend:,.0f} ₽\n\n"

    return result


@tool
def get_bottom_margin_sku(date: str, n: int = 10) -> str:
    """
    Получить SKU с наименьшей/отрицательной маржей (убыточные).

    Args:
        date: Дата в формате YYYY-MM-DD
        n: Количество позиций (по умолчанию 10)

    Returns:
        Список убыточных/низкомаржинальных SKU
    """
    response = supabase.table("wb_margin_daily") \
        .select("*") \
        .eq("date", date) \
        .order("margin_profit_after_ads", desc=False) \
        .limit(n) \
        .execute()

    if not response.data:
        return f"Нет данных за {date}"

    result = f"Убыточные/низкомаржинальные SKU за {date}:\n\n"

    for i, row in enumerate(response.data, 1):
        title = row['title'][:35] if row['title'] else str(row['nmid'])
        margin = row['margin_profit_after_ads'] or 0
        margin_pct = row['margin_percent_after_ads'] or 0
        revenue = row['revenue_total'] or 0
        ad_spend = row['ad_spend'] or 0

        status = "🔴 УБЫТОК" if margin < 0 else "🟡 Низкая маржа"

        result += f"{i}. {title}...\n"
        result += f"   {status}: {margin:,.0f} ₽ ({margin_pct:.1f}%)\n"
        result += f"   Выручка: {revenue:,.0f} ₽, Реклама: {ad_spend:,.0f} ₽\n\n"

    return result


if __name__ == "__main__":
    print("=== Сводка по марже ===")
    print(get_margin_summary.invoke({"date": "2026-01-16"}))

    print("\n=== Тренд маржи ===")
    print(get_margin_trend.invoke({"days": 7}))

    print("\n=== Топ-5 по марже ===")
    print(get_top_margin_sku.invoke({"date": "2026-01-16", "n": 5}))

    print("\n=== Убыточные SKU ===")
    print(get_bottom_margin_sku.invoke({"date": "2026-01-16", "n": 5}))
