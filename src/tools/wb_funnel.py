# src/tools/wb_funnel.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase


@tool
def get_funnel_summary(date: str) -> str:
    """
    Получить сводку по воронке продаж за день.

    Args:
        date: Дата в формате YYYY-MM-DD (поле reportdate)

    Returns:
        Воронка: просмотры → корзина → заказы → выкупы с конверсиями
    """
    response = supabase.table("wb_sales_funnel_products") \
        .select("*") \
        .eq("reportdate", date) \
        .execute()

    if not response.data:
        return f"Нет данных по воронке за {date}"

    df = pd.DataFrame(response.data)

    # Агрегация
    total_views = df["opencount"].sum()
    total_cart = df["cartcount"].sum()
    total_orders = df["ordercount"].sum()
    total_order_sum = df["ordersum"].sum()
    total_buyout = df["buyoutcount"].sum()
    total_buyout_sum = df["buyoutsum"].sum()

    # Конверсии
    cr_view_to_cart = (total_cart / total_views * 100) if total_views > 0 else 0
    cr_cart_to_order = (total_orders / total_cart * 100) if total_cart > 0 else 0
    cr_order_to_buyout = (total_buyout / total_orders * 100) if total_orders > 0 else 0
    cr_total = (total_orders / total_views * 100) if total_views > 0 else 0

    result = f"""Воронка продаж WB за {date}:

👁️ ПРОСМОТРЫ: {total_views:,}

   ↓ CR {cr_view_to_cart:.2f}%

🛒 КОРЗИНА: {total_cart:,}

   ↓ CR {cr_cart_to_order:.2f}%

📦 ЗАКАЗЫ: {total_orders:,} ({total_order_sum:,.0f} ₽)

   ↓ CR {cr_order_to_buyout:.1f}%

✅ ВЫКУПЫ: {total_buyout:,} ({total_buyout_sum:,.0f} ₽)

Общая конверсия (просмотр→заказ): {cr_total:.2f}%
Средний чек заказа: {total_order_sum / total_orders:,.0f} ₽
"""

    return result


@tool
def get_stock_summary(date: str) -> str:
    """
    Получить сводку по остаткам.

    Args:
        date: Дата в формате YYYY-MM-DD (поле reportdate)

    Returns:
        Сводка по остаткам: в наличии, нет в наличии, критически мало
    """
    response = supabase.table("wb_sales_funnel_products") \
        .select("nmid, title, stocks, ordercount") \
        .eq("reportdate", date) \
        .execute()

    if not response.data:
        return f"Нет данных по остаткам за {date}"

    df = pd.DataFrame(response.data)

    # Категории
    out_of_stock = df[df["stocks"] == 0]
    critical = df[(df["stocks"] > 0) & (df["stocks"] < 50)]
    normal = df[df["stocks"] >= 50]

    result = f"""Сводка по остаткам на {date}:

✅ В наличии (>50 шт): {len(normal)} SKU
🟡 Критически мало (<50 шт): {len(critical)} SKU
🔴 Нет в наличии: {len(out_of_stock)} SKU

"""

    # Детали по критическим
    if not critical.empty:
        result += "⚠️ Критически мало остатков:\n"
        critical_sorted = critical.sort_values("stocks")
        for _, row in critical_sorted.head(10).iterrows():
            title = row['title'][:30] if row['title'] else str(row['nmid'])
            result += f"• {title}: {row['stocks']} шт\n"

    # Детали по out of stock с заказами
    if not out_of_stock.empty:
        oos_with_orders = out_of_stock[out_of_stock["ordercount"] > 0]
        if not oos_with_orders.empty:
            result += "\n🔴 Нет в наличии (но были заказы!):\n"
            for _, row in oos_with_orders.iterrows():
                title = row['title'][:30] if row['title'] else str(row['nmid'])
                result += f"• {title}: заказов {row['ordercount']}\n"

    return result


@tool
def get_low_conversion_sku(date: str, min_views: int = 100, max_cr: float = 2.0) -> str:
    """
    Найти SKU с низкой конверсией (много просмотров, мало заказов).

    Args:
        date: Дата в формате YYYY-MM-DD
        min_views: Минимум просмотров для анализа (по умолчанию 100)
        max_cr: Максимальный CR для попадания в список (по умолчанию 2%)

    Returns:
        Список SKU с низкой конверсией — кандидаты на оптимизацию карточки
    """
    response = supabase.table("wb_sales_funnel_products") \
        .select("*") \
        .eq("reportdate", date) \
        .gte("opencount", min_views) \
        .execute()

    if not response.data:
        return f"Нет данных за {date} с просмотрами >= {min_views}"

    df = pd.DataFrame(response.data)

    # Считаем CR
    df["cr"] = df.apply(
        lambda row: (row["ordercount"] / row["opencount"] * 100)
        if row["opencount"] > 0 else 0,
        axis=1
    )

    # Фильтруем по низкому CR
    low_cr = df[df["cr"] < max_cr].sort_values("opencount", ascending=False)

    if low_cr.empty:
        return f"Нет SKU с CR < {max_cr}% за {date}"

    result = f"SKU с низкой конверсией за {date}:\n"
    result += f"(просмотров >= {min_views}, CR < {max_cr}%)\n\n"

    for _, row in low_cr.head(10).iterrows():
        title = row['title'][:35] if row['title'] else str(row['nmid'])

        result += f"• {title}\n"
        result += f"  Просмотров: {row['opencount']:,}, Заказов: {row['ordercount']}\n"
        result += f"  CR: {row['cr']:.2f}%, В корзину: {row['cartcount']}\n"
        result += f"  Остаток: {row['stocks']} шт\n\n"

    return result


if __name__ == "__main__":
    print("=== Воронка продаж ===")
    print(get_funnel_summary.invoke({"date": "2026-01-16"}))

    print("\n=== Остатки ===")
    print(get_stock_summary.invoke({"date": "2026-01-16"}))

    print("\n=== Низкая конверсия ===")
    print(get_low_conversion_sku.invoke({"date": "2026-01-16", "min_views": 50, "max_cr": 3.0}))
