# src/tools/analytics.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase

# Константа — легко менять в одном месте
TABLE_UNIT_ECONOMICS = "wb_margin_daily"

@tool
def get_daily_summary(date: str) -> str:
    """
    Получить сводку по всем артикулам за конкретный день.
    
    Args:
        date: Дата в формате YYYY-MM-DD (например, '2026-01-01')
    
    Returns:
        Сводка: выручка, заказы, расход на рекламу, маржа
    """
    response = supabase.table("wb_margin_daily") \
        .select("*") \
        .eq("date", date) \
        .execute()
    
    if not response.data:
        return f"Нет данных за {date}"
    
    df = pd.DataFrame(response.data)
    
    summary = {
        "Дата": date,
        "Артикулов": len(df),
        "Заказов": int(df["ordercount"].sum()),
        "Выручка": f"{df['revenue_total'].sum():,.0f} ₽",
        "Расход на рекламу": f"{df['ad_spend'].sum():,.0f} ₽",
        "Маржа (после рекламы)": f"{df['margin_profit_after_ads'].sum():,.0f} ₽",
        "Маржинальность": f"{df['margin_percent_after_ads'].mean():.1f}%"
    }
    
    return "\n".join([f"{k}: {v}" for k, v in summary.items()])

# Добавь в src/tools/analytics.py после первого tool

@tool
def get_top_sku(date: str, metric: str = "margin_profit_after_ads", n: int = 5) -> str:
    """
    Получить топ артикулов по выбранной метрике.
    
    Args:
        date: Дата в формате YYYY-MM-DD
        metric: Метрика для сортировки (margin_profit_after_ads, revenue_total, ordercount)
        n: Количество позиций в топе
    
    Returns:
        Топ-N артикулов с показателями
    """
    response = supabase.table(TABLE_UNIT_ECONOMICS) \
        .select("*") \
        .eq("date", date) \
        .execute()
    
    if not response.data:
        return f"Нет данных за {date}"
    
    df = pd.DataFrame(response.data)
    top = df.nlargest(n, metric)[["nmid", "title", "ordercount", "revenue_total", "margin_profit_after_ads"]]
    
    result = f"Топ-{n} по {metric} за {date}:\n\n"
    for i, row in top.iterrows():
        result += f"• {row['title'][:30]}...\n"
        result += f"  Заказов: {row['ordercount']}, Выручка: {row['revenue_total']:,.0f} ₽, Маржа: {row['margin_profit_after_ads']:,.0f} ₽\n\n"
    
    return result


@tool
def get_unprofitable_sku(date: str, threshold: float = 0) -> str:
    """
    Найти убыточные артикулы (маржа ниже порога).
    
    Args:
        date: Дата в формате YYYY-MM-DD
        threshold: Порог маржинальности в % (по умолчанию 0 - убыточные)
    
    Returns:
        Список убыточных артикулов
    """
    response = supabase.table(TABLE_UNIT_ECONOMICS) \
        .select("*") \
        .eq("date", date) \
        .execute()
    
    if not response.data:
        return f"Нет данных за {date}"
    
    df = pd.DataFrame(response.data)
    unprofitable = df[df["margin_percent_after_ads"] < threshold]
    
    if unprofitable.empty:
        return f"Убыточных артикулов (маржа < {threshold}%) за {date} не найдено"
    
    result = f"Убыточные артикулы за {date} (маржа < {threshold}%):\n\n"
    for i, row in unprofitable.iterrows():
        result += f"• {row['title'][:30]}...\n"
        result += f"  Маржинальность: {row['margin_percent_after_ads']:.1f}%, Маржа: {row['margin_profit_after_ads']:,.0f} ₽\n\n"
    
    return result


# === Обновлённый тест ===
if __name__ == "__main__":
    print("=== Сводка за день ===")
    print(get_daily_summary.invoke({"date": "2026-01-16"}))
    
    print("\n=== Топ-5 по марже ===")
    print(get_top_sku.invoke({"date": "2026-01-16", "metric": "margin_profit_after_ads", "n": 5}))
    
    print("\n=== Убыточные артикулы ===")
    print(get_unprofitable_sku.invoke({"date": "2026-01-16", "threshold": 10}))

