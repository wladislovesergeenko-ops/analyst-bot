# src/tools/wb_plan.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase


@tool
def get_plan_fact_summary() -> str:
    """
    Получить сводку выполнения плана по марже на текущий месяц.

    Returns:
        Общее выполнение плана и топ отстающих/лидирующих SKU
    """
    response = supabase.table("v_plan_fact_margin") \
        .select("*") \
        .execute()

    if not response.data:
        return "Нет данных по плану/факту"

    df = pd.DataFrame(response.data)

    # Общие показатели
    total_plan = df["plan_margin_profit"].sum()
    total_plan_to_date = df["plan_margin_to_date"].sum()
    total_fact = df["fact_margin_profit"].sum()

    overall_completion = (total_fact / total_plan_to_date * 100) if total_plan_to_date > 0 else 0

    # Статус
    if overall_completion >= 100:
        status = "✅ План выполняется"
    elif overall_completion >= 85:
        status = "🟡 Небольшое отставание"
    else:
        status = "🔴 Критическое отставание"

    result = f"""Выполнение плана по марже:

{status}

Общий план на месяц: {total_plan:,.0f} ₽
Линейный план на сегодня: {total_plan_to_date:,.0f} ₽
Факт на сегодня: {total_fact:,.0f} ₽
Выполнение: {overall_completion:.0f}%
Отклонение: {total_fact - total_plan_to_date:+,.0f} ₽
"""

    # Топ отстающих
    df_valid = df[df["plan_margin_to_date"] > 0].copy()
    if not df_valid.empty:
        df_valid["gap"] = df_valid["fact_margin_profit"] - df_valid["plan_margin_to_date"]
        df_valid["completion"] = df_valid["plan_completion_percent"]

        underperformers = df_valid.nsmallest(5, "gap")

        result += "\n📉 Топ-5 отстающих от плана:\n"
        for _, row in underperformers.iterrows():
            title = row['title'][:30] if row['title'] else str(row['nmid'])
            result += f"• {title}: {row['completion']:.0f}% ({row['gap']:+,.0f} ₽)\n"

        # Топ лидеров
        overperformers = df_valid.nlargest(5, "gap")

        result += "\n📈 Топ-5 перевыполняющих план:\n"
        for _, row in overperformers.iterrows():
            title = row['title'][:30] if row['title'] else str(row['nmid'])
            result += f"• {title}: {row['completion']:.0f}% ({row['gap']:+,.0f} ₽)\n"

    return result


@tool
def get_underperforming_sku(threshold: float = 80.0) -> str:
    """
    Получить SKU, которые отстают от плана.

    Args:
        threshold: Порог выполнения плана в % (по умолчанию 80%)

    Returns:
        Список SKU с выполнением ниже порога
    """
    response = supabase.table("v_plan_fact_margin") \
        .select("*") \
        .execute()

    if not response.data:
        return "Нет данных по плану/факту"

    df = pd.DataFrame(response.data)

    # Фильтруем только те, у кого есть план
    df = df[df["plan_margin_to_date"] > 0]

    # Отстающие от порога
    underperformers = df[df["plan_completion_percent"] < threshold].copy()

    if underperformers.empty:
        return f"Нет SKU с выполнением плана ниже {threshold}%"

    underperformers["gap"] = underperformers["fact_margin_profit"] - underperformers["plan_margin_to_date"]
    underperformers = underperformers.sort_values("gap")

    total_gap = underperformers["gap"].sum()

    result = f"SKU с выполнением плана < {threshold}%:\n"
    result += f"Всего: {len(underperformers)} SKU, общее отставание: {total_gap:,.0f} ₽\n\n"

    for _, row in underperformers.iterrows():
        title = row['title'][:35] if row['title'] else str(row['nmid'])
        result += f"• {title}\n"
        result += f"  План: {row['plan_margin_to_date']:,.0f} ₽ → Факт: {row['fact_margin_profit']:,.0f} ₽\n"
        result += f"  Выполнение: {row['plan_completion_percent']:.0f}%, Отставание: {row['gap']:,.0f} ₽\n\n"

    return result


@tool
def get_plan_forecast() -> str:
    """
    Прогноз выполнения плана на конец месяца по текущему темпу.

    Returns:
        Прогноз маржи на конец месяца
    """
    response = supabase.table("v_plan_fact_margin") \
        .select("*") \
        .execute()

    if not response.data:
        return "Нет данных по плану/факту"

    df = pd.DataFrame(response.data)

    total_plan = df["plan_margin_profit"].sum()
    total_fact = df["fact_margin_profit"].sum()

    # Предполагаем что days_passed и days_in_month одинаковы для всех строк
    if df["days_passed"].iloc[0] > 0:
        days_passed = df["days_passed"].iloc[0]
        days_in_month = df["days_in_month"].iloc[0]
        days_left = days_in_month - days_passed

        # Текущий темп в день
        daily_rate = total_fact / days_passed

        # Прогноз на конец месяца
        forecast = total_fact + (daily_rate * days_left)
        forecast_completion = (forecast / total_plan * 100) if total_plan > 0 else 0

        # Требуемый темп для выполнения плана
        remaining_plan = total_plan - total_fact
        required_daily = remaining_plan / days_left if days_left > 0 else 0

        status = "✅ План будет выполнен" if forecast >= total_plan else "⚠️ План под угрозой"

        result = f"""Прогноз выполнения плана:

{status}

Дней прошло: {int(days_passed)} из {int(days_in_month)}
Текущий факт: {total_fact:,.0f} ₽
Текущий темп: {daily_rate:,.0f} ₽/день

📊 Прогноз на конец месяца: {forecast:,.0f} ₽ ({forecast_completion:.0f}% от плана)

План на месяц: {total_plan:,.0f} ₽
Осталось набрать: {remaining_plan:,.0f} ₽
Требуемый темп: {required_daily:,.0f} ₽/день

Разница темпов: {daily_rate - required_daily:+,.0f} ₽/день
"""
        return result

    return "Недостаточно данных для прогноза"


if __name__ == "__main__":
    print("=== План/Факт сводка ===")
    print(get_plan_fact_summary.invoke({}))

    print("\n=== Отстающие SKU ===")
    print(get_underperforming_sku.invoke({"threshold": 80}))

    print("\n=== Прогноз на месяц ===")
    print(get_plan_forecast.invoke({}))
