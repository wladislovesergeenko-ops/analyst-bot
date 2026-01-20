# src/tools/ads.py

import pandas as pd
from langchain_core.tools import tool
from src.db.supabase import supabase

TABLE_ADS = "v_ads_daily_performance"


@tool
def get_ads_summary(date: str) -> str:
    """
    Получить общую сводку по рекламе за день.
    
    Args:
        date: Дата в формате YYYY-MM-DD
    
    Returns:
        Сводка: расход, заказы, выручка, ДРР
    """
    response = supabase.table(TABLE_ADS) \
        .select("*") \
        .eq("date", date) \
        .execute()
    
    if not response.data:
        return f"Нет данных по рекламе за {date}"
    
    df = pd.DataFrame(response.data)
    
    total_spend = df["ad_spend"].sum()
    total_revenue = df["ad_revenue"].sum()
    total_orders = df["orders"].sum()
    drr = (total_spend / total_revenue * 100) if total_revenue > 0 else 0
    
    summary = {
        "Дата": date,
        "Кампаний": len(df),
        "Расход": f"{total_spend:,.0f} ₽",
        "Заказов": int(total_orders),
        "Выручка": f"{total_revenue:,.0f} ₽",
        "ДРР": f"{drr:.1f}%"
    }
    
    return "\n".join([f"{k}: {v}" for k, v in summary.items()])


# В src/tools/ads.py обнови функцию get_high_drr_campaigns:

@tool
def get_high_drr_campaigns(date: str, threshold: float = 15.0) -> str:
    """
    Найти кампании с высоким ДРР, требующие оптимизации.
    
    Args:
        date: Дата в формате YYYY-MM-DD
        threshold: Порог ДРР в процентах (по умолчанию 15%)
    
    Returns:
        Список кампаний с высоким ДРР, ставками и зависимостью от рекламы
    """
    response = supabase.table(TABLE_ADS) \
        .select("*") \
        .eq("date", date) \
        .gt("drr", threshold) \
        .execute()
    
    if not response.data:
        return f"Кампаний с ДРР > {threshold}% за {date} не найдено"
    
    df = pd.DataFrame(response.data)
    df = df.sort_values("ad_spend", ascending=False)
    
    result = f"Кампании с ДРР > {threshold}% за {date}:\n\n"
    for _, row in df.iterrows():
        ad_share = row.get('ad_revenue_share', 0) or 0
        is_dependent = "⚠️ ВЫСОКАЯ ЗАВИСИМОСТЬ" if ad_share > 50 else ""
        
        result += f"• {row['campaign_name'][:40]}\n"
        result += f"  Расход: {row['ad_spend']:,.0f} ₽, Выручка рекл: {row['ad_revenue']:,.0f} ₽\n"
        result += f"  ДРР: {row['drr']:.1f}%, CR: {row['cr']:.1f}%\n"
        result += f"  Доля рекламной выручки: {ad_share:.0f}% {is_dependent}\n"
        result += f"  Ставки: поиск {row['bid_search_rub']:.0f} ₽, каталог {row['bid_recommendations_rub']:.0f} ₽\n\n"
    
    return result


@tool
def get_scalable_campaigns(date: str) -> str:
    """
    Найти кампании для масштабирования (CR > 8% и ДРР < 15%).
    
    Args:
        date: Дата в формате YYYY-MM-DD
    
    Returns:
        Список кампаний, которые можно масштабировать
    """
    response = supabase.table(TABLE_ADS) \
        .select("*") \
        .eq("date", date) \
        .eq("is_scalable", True) \
        .execute()
    
    if not response.data:
        return f"Кампаний для масштабирования за {date} не найдено"
    
    df = pd.DataFrame(response.data)
    df = df.sort_values("orders", ascending=False)
    
    result = f"Кампании для масштабирования за {date}:\n\n"
    for _, row in df.iterrows():
        result += f"• {row['campaign_name'][:40]}\n"
        result += f"  Заказов: {row['orders']}, CR: {row['cr']:.1f}%, ДРР: {row['drr']:.1f}%\n"
        result += f"  Ставки: поиск {row['bid_search_rub']:.0f} ₽, каталог {row['bid_recommendations_rub']:.0f} ₽\n\n"
    
    return result
# Добавь в src/tools/ads.py

@tool
def get_ads_trend(metric: str, days: int = 7) -> str:
    """
    Показать динамику любой метрики рекламы за N дней.
    
    Args:
        metric: Метрика для анализа. Доступные:
            - views (показы)
            - clicks (клики)
            - orders (заказы)
            - ad_spend (расход)
            - ad_revenue (выручка с рекламы)
            - ctr (CTR %)
            - cr (конверсия клик→заказ %)
            - cpc (цена клика)
            - drr (ДРР %)
            - ad_revenue_share (доля рекламной выручки %)
        days: Количество дней (по умолчанию 7)
    
    Returns:
        Динамика метрики по дням
    """
    ALLOWED_METRICS = {
        'views': 'Показы',
        'clicks': 'Клики', 
        'orders': 'Заказы',
        'ad_spend': 'Расход ₽',
        'ad_revenue': 'Выручка с рекламы ₽',
        'ctr': 'CTR %',
        'cr': 'CR %',
        'cpc': 'CPC ₽',
        'drr': 'ДРР %',
        'ad_revenue_share': 'Доля рекламной выручки %'
    }
    
    if metric not in ALLOWED_METRICS:
        return f"Неизвестная метрика '{metric}'. Доступные: {', '.join(ALLOWED_METRICS.keys())}"
    
    response = supabase.table(TABLE_ADS) \
        .select("*") \
        .order("date", desc=True) \
        .limit(1000) \
        .execute()
    
    if not response.data:
        return "Нет данных по рекламе"
    
    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Фильтруем по количеству дней
    max_date = df['date'].max()
    min_date = max_date - pd.Timedelta(days=days-1)
    df = df[df['date'] >= min_date]
    
    # Агрегируем по дням
    if metric in ['ctr', 'cr', 'drr', 'cpc', 'ad_revenue_share']:
        # Для процентов и средних — считаем средневзвешенное
        daily = df.groupby('date')[metric].mean().round(2)
    else:
        # Для абсолютных значений — сумма
        daily = df.groupby('date')[metric].sum().round(0)
    
    daily = daily.sort_index()
    
    # Формируем ответ
    metric_name = ALLOWED_METRICS[metric]
    result = f"Динамика '{metric_name}' за {days} дней:\n\n"
    
    for date, value in daily.items():
        date_str = date.strftime("%d.%m")
        if metric in ['ad_spend', 'ad_revenue', 'cpc']:
            result += f"{date_str}: {value:,.0f} ₽\n"
        elif metric in ['ctr', 'cr', 'drr', 'ad_revenue_share']:
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


# Добавь в src/tools/ads.py

@tool
def compare_ads_periods(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
) -> str:
    """
    Сравнить показатели рекламы за два периода.
    
    Args:
        period1_start: Начало первого периода (YYYY-MM-DD)
        period1_end: Конец первого периода (YYYY-MM-DD)
        period2_start: Начало второго периода (YYYY-MM-DD)
        period2_end: Конец второго периода (YYYY-MM-DD)
    
    Returns:
        Сравнение ключевых метрик: расход, заказы, выручка, ДРР, клики, CPC
    """
    response = supabase.table(TABLE_ADS) \
        .select("*") \
        .gte("date", period1_start) \
        .lte("date", period2_end) \
        .execute()
    
    if not response.data:
        return "Нет данных за указанные периоды"
    
    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Разделяем на два периода
    p1 = df[(df['date'] >= period1_start) & (df['date'] <= period1_end)]
    p2 = df[(df['date'] >= period2_start) & (df['date'] <= period2_end)]
    
    def calc_metrics(data):
        spend = data['ad_spend'].sum()
        revenue = data['ad_revenue'].sum()
        orders = data['orders'].sum()
        clicks = data['clicks'].sum()
        views = data['views'].sum()
        
        drr = (spend / revenue * 100) if revenue > 0 else 0
        cr = (orders / clicks * 100) if clicks > 0 else 0
        ctr = (clicks / views * 100) if views > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        
        return {
            'spend': spend,
            'revenue': revenue,
            'orders': orders,
            'clicks': clicks,
            'drr': drr,
            'ctr': ctr,
            'cr': cr,
            'cpc': cpc
        }
    
    m1 = calc_metrics(p1)
    m2 = calc_metrics(p2)
    
    def calc_change(old, new):
        if old == 0:
            return 0
        return ((new - old) / old) * 100
    
    def format_change(change):
        emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        return f"{emoji} {change:+.1f}%"
    
    result = f"""Сравнение периодов:
Период 1: {period1_start} — {period1_end}
Период 2: {period2_start} — {period2_end}

| Метрика | Период 1 | Период 2 | Изменение |
|---------|----------|----------|-----------|
| Расход | {m1['spend']:,.0f} ₽ | {m2['spend']:,.0f} ₽ | {format_change(calc_change(m1['spend'], m2['spend']))} |
| Выручка | {m1['revenue']:,.0f} ₽ | {m2['revenue']:,.0f} ₽ | {format_change(calc_change(m1['revenue'], m2['revenue']))} |
| Заказы | {m1['orders']:,.0f} | {m2['orders']:,.0f} | {format_change(calc_change(m1['orders'], m2['orders']))} |
| Клики | {m1['clicks']:,.0f} | {m2['clicks']:,.0f} | {format_change(calc_change(m1['clicks'], m2['clicks']))} |
| ДРР | {m1['drr']:.1f}% | {m2['drr']:.1f}% | {format_change(calc_change(m1['drr'], m2['drr']))} |
| CR | {m1['cr']:.1f}% | {m2['cr']:.1f}% | {format_change(calc_change(m1['cr'], m2['cr']))} |
| CTR | {m1['ctr']:.2f}% | {m2['ctr']:.2f}% | {format_change(calc_change(m1['ctr'], m2['ctr']))} |
| CPC | {m1['cpc']:.1f} ₽ | {m2['cpc']:.1f} ₽ | {format_change(calc_change(m1['cpc'], m2['cpc']))} |
"""
    
    return result


if __name__ == "__main__":
    print("=== Сводка по рекламе ===")
    print(get_ads_summary.invoke({"date": "2026-01-16"}))
    
    print("\n=== Кампании с высоким ДРР ===")
    print(get_high_drr_campaigns.invoke({"date": "2026-01-16"}))
    
    print("\n=== Кампании для масштабирования ===")
    print(get_scalable_campaigns.invoke({"date": "2026-01-16"}))
    
    print("\n=== Тренд ДРР за 7 дней ===")
    print(get_ads_trend.invoke({"metric": "drr", "days": 7}))
    
    print("\n=== Тренд расхода за 7 дней ===")
    print(get_ads_trend.invoke({"metric": "ad_spend", "days": 7}))
    print("\n=== Сравнение недель ===")
    print(compare_ads_periods.invoke({
        "period1_start": "2026-01-06",
        "period1_end": "2026-01-12",
        "period2_start": "2026-01-13",
        "period2_end": "2026-01-16"
}))