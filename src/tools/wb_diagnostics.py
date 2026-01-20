# src/tools/wb_diagnostics.py

"""
Tier 2: Diagnostic Analytics Tools

Инструменты для диагностики — "почему произошло?"
"""

import pandas as pd
from datetime import datetime, timedelta
from langchain_core.tools import tool
from src.db.supabase import supabase


@tool
def compare_periods(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
) -> str:
    """
    Сравнить два периода по ключевым метрикам.

    Args:
        period1_start: Начало первого периода (YYYY-MM-DD)
        period1_end: Конец первого периода (YYYY-MM-DD)
        period2_start: Начало второго периода (YYYY-MM-DD)
        period2_end: Конец второго периода (YYYY-MM-DD)

    Returns:
        Сравнение метрик: маржа, выручка, заказы, реклама
    """
    # Получаем данные по марже
    response = supabase.table("wb_margin_daily") \
        .select("date, margin_profit_after_ads, revenue_total, ad_spend, ordercount") \
        .gte("date", period1_start) \
        .lte("date", period2_end) \
        .execute()

    if not response.data:
        return "Нет данных за указанные периоды"

    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])

    # Разделяем периоды
    p1 = df[(df['date'] >= period1_start) & (df['date'] <= period1_end)]
    p2 = df[(df['date'] >= period2_start) & (df['date'] <= period2_end)]

    def calc_metrics(data):
        return {
            'margin': data['margin_profit_after_ads'].sum(),
            'revenue': data['revenue_total'].sum(),
            'orders': data['ordercount'].sum(),
            'ad_spend': data['ad_spend'].sum(),
            'days': len(data['date'].unique())
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

    # Средние в день
    m1_daily_margin = m1['margin'] / m1['days'] if m1['days'] > 0 else 0
    m2_daily_margin = m2['margin'] / m2['days'] if m2['days'] > 0 else 0

    result = f"""Сравнение периодов:

Период 1: {period1_start} — {period1_end} ({m1['days']} дн.)
Период 2: {period2_start} — {period2_end} ({m2['days']} дн.)

| Метрика | Период 1 | Период 2 | Изменение |
|---------|----------|----------|-----------|
| Маржа | {m1['margin']:,.0f} ₽ | {m2['margin']:,.0f} ₽ | {format_change(calc_change(m1['margin'], m2['margin']))} |
| Маржа/день | {m1_daily_margin:,.0f} ₽ | {m2_daily_margin:,.0f} ₽ | {format_change(calc_change(m1_daily_margin, m2_daily_margin))} |
| Выручка | {m1['revenue']:,.0f} ₽ | {m2['revenue']:,.0f} ₽ | {format_change(calc_change(m1['revenue'], m2['revenue']))} |
| Заказы | {m1['orders']:,.0f} | {m2['orders']:,.0f} | {format_change(calc_change(m1['orders'], m2['orders']))} |
| Реклама | {m1['ad_spend']:,.0f} ₽ | {m2['ad_spend']:,.0f} ₽ | {format_change(calc_change(m1['ad_spend'], m2['ad_spend']))} |

Δ Маржа: {m2['margin'] - m1['margin']:+,.0f} ₽
"""

    return result


@tool
def analyze_margin_change(days_back: int = 7) -> str:
    """
    Анализ причин изменения маржи за последние N дней.

    Проверяет: цены, трафик, конверсию, рекламу.

    Args:
        days_back: За сколько дней анализировать (по умолчанию 7)

    Returns:
        Диагностика с выявленными причинами изменения
    """
    today = datetime.now()
    period2_end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    period2_start = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    period1_end = (today - timedelta(days=days_back + 1)).strftime("%Y-%m-%d")
    period1_start = (today - timedelta(days=days_back * 2)).strftime("%Y-%m-%d")

    # Данные по марже
    margin_response = supabase.table("wb_margin_daily") \
        .select("*") \
        .gte("date", period1_start) \
        .lte("date", period2_end) \
        .execute()

    # Данные по воронке
    funnel_response = supabase.table("wb_sales_funnel_products") \
        .select("reportdate, opencount, cartcount, ordercount") \
        .gte("reportdate", period1_start) \
        .lte("reportdate", period2_end) \
        .execute()

    # Данные по ценам
    price_response = supabase.table("wb_spp_daily") \
        .select("date, finished_price") \
        .gte("date", period1_start) \
        .lte("date", period2_end) \
        .execute()

    insights = []

    # Анализ маржи
    if margin_response.data:
        df = pd.DataFrame(margin_response.data)
        df['date'] = pd.to_datetime(df['date'])

        p1 = df[(df['date'] >= period1_start) & (df['date'] <= period1_end)]
        p2 = df[(df['date'] >= period2_start) & (df['date'] <= period2_end)]

        m1_margin = p1['margin_profit_after_ads'].sum()
        m2_margin = p2['margin_profit_after_ads'].sum()
        margin_change = ((m2_margin - m1_margin) / m1_margin * 100) if m1_margin != 0 else 0

        m1_ad = p1['ad_spend'].sum()
        m2_ad = p2['ad_spend'].sum()
        ad_change = ((m2_ad - m1_ad) / m1_ad * 100) if m1_ad != 0 else 0

        if abs(margin_change) > 10:
            direction = "выросла" if margin_change > 0 else "упала"
            insights.append(f"📊 Маржа {direction} на {abs(margin_change):.0f}%")

        if abs(ad_change) > 20:
            direction = "вырос" if ad_change > 0 else "снизился"
            insights.append(f"📢 Расход на рекламу {direction} на {abs(ad_change):.0f}%")

    # Анализ воронки
    if funnel_response.data:
        df = pd.DataFrame(funnel_response.data)
        df['reportdate'] = pd.to_datetime(df['reportdate'])

        p1 = df[(df['reportdate'] >= period1_start) & (df['reportdate'] <= period1_end)]
        p2 = df[(df['reportdate'] >= period2_start) & (df['reportdate'] <= period2_end)]

        p1_views = p1['opencount'].sum()
        p2_views = p2['opencount'].sum()
        views_change = ((p2_views - p1_views) / p1_views * 100) if p1_views != 0 else 0

        p1_orders = p1['ordercount'].sum()
        p2_orders = p2['ordercount'].sum()

        p1_cr = (p1_orders / p1_views * 100) if p1_views > 0 else 0
        p2_cr = (p2_orders / p2_views * 100) if p2_views > 0 else 0
        cr_change = p2_cr - p1_cr

        if abs(views_change) > 15:
            direction = "вырос" if views_change > 0 else "упал"
            insights.append(f"👁️ Трафик {direction} на {abs(views_change):.0f}%")

        if abs(cr_change) > 0.5:
            direction = "выросла" if cr_change > 0 else "упала"
            insights.append(f"📈 Конверсия {direction}: {p1_cr:.2f}% → {p2_cr:.2f}%")

    # Анализ цен
    if price_response.data:
        df = pd.DataFrame(price_response.data)
        df['date'] = pd.to_datetime(df['date'])

        p1 = df[(df['date'] >= period1_start) & (df['date'] <= period1_end)]
        p2 = df[(df['date'] >= period2_start) & (df['date'] <= period2_end)]

        p1_price = p1['finished_price'].mean()
        p2_price = p2['finished_price'].mean()
        price_change = ((p2_price - p1_price) / p1_price * 100) if p1_price != 0 else 0

        if abs(price_change) > 5:
            direction = "выросла" if price_change > 0 else "снизилась"
            insights.append(f"💰 Средняя цена {direction} на {abs(price_change):.1f}%")

    # Формируем результат
    result = f"""Диагностика изменений за последние {days_back} дней:

Сравниваю:
- Период 1: {period1_start} — {period1_end}
- Период 2: {period2_start} — {period2_end}

"""

    if insights:
        result += "🔍 Выявленные факторы:\n\n"
        for insight in insights:
            result += f"• {insight}\n"
    else:
        result += "✅ Значительных изменений не выявлено"

    return result


@tool
def find_margin_anomalies(days: int = 7) -> str:
    """
    Найти SKU с аномальными изменениями маржи.

    Args:
        days: За сколько дней искать аномалии

    Returns:
        Список SKU с резкими изменениями маржи
    """
    today = datetime.now()
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days + 7)).strftime("%Y-%m-%d")  # +7 для сравнения

    response = supabase.table("wb_margin_daily") \
        .select("date, nmid, title, margin_profit_after_ads, revenue_total") \
        .gte("date", start_date) \
        .lte("date", end_date) \
        .execute()

    if not response.data:
        return "Нет данных для анализа аномалий"

    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])

    # Средняя маржа по SKU за первую половину периода vs вторую
    mid_date = today - timedelta(days=days)

    anomalies = []

    for nmid in df['nmid'].unique():
        sku_data = df[df['nmid'] == nmid]

        early = sku_data[sku_data['date'] < mid_date.strftime("%Y-%m-%d")]
        late = sku_data[sku_data['date'] >= mid_date.strftime("%Y-%m-%d")]

        if len(early) > 0 and len(late) > 0:
            early_margin = early['margin_profit_after_ads'].mean()
            late_margin = late['margin_profit_after_ads'].mean()

            if early_margin != 0:
                change = ((late_margin - early_margin) / abs(early_margin)) * 100

                if abs(change) > 50:  # Более 50% изменение
                    title = sku_data['title'].iloc[0] if sku_data['title'].iloc[0] else str(nmid)
                    anomalies.append({
                        'nmid': nmid,
                        'title': title[:30],
                        'early_margin': early_margin,
                        'late_margin': late_margin,
                        'change': change
                    })

    if not anomalies:
        return f"Аномальных изменений маржи за {days} дней не найдено"

    # Сортируем по абсолютному изменению
    anomalies.sort(key=lambda x: abs(x['change']), reverse=True)

    result = f"SKU с аномальными изменениями маржи за {days} дней:\n\n"

    for a in anomalies[:10]:
        emoji = "📈" if a['change'] > 0 else "📉"
        result += f"{emoji} {a['title']}...\n"
        result += f"   Было: {a['early_margin']:,.0f} ₽/день → Стало: {a['late_margin']:,.0f} ₽/день\n"
        result += f"   Изменение: {a['change']:+.0f}%\n\n"

    return result


@tool
def diagnose_sku(nmid: int, days: int = 7) -> str:
    """
    Детальная диагностика конкретного SKU.

    Проверяет все факторы: цена, трафик, конверсия, реклама, остатки.

    Args:
        nmid: ID артикула
        days: За сколько дней анализировать

    Returns:
        Полная диагностика SKU с выводами
    """
    today = datetime.now()
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    mid_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    # Маржа
    margin_resp = supabase.table("wb_margin_daily") \
        .select("*") \
        .eq("nmid", nmid) \
        .gte("date", start_date) \
        .lte("date", end_date) \
        .execute()

    # Воронка
    funnel_resp = supabase.table("wb_sales_funnel_products") \
        .select("*") \
        .eq("nmid", nmid) \
        .gte("reportdate", start_date) \
        .lte("reportdate", end_date) \
        .execute()

    # Цены
    price_resp = supabase.table("wb_spp_daily") \
        .select("*") \
        .eq("nmid", nmid) \
        .gte("date", start_date) \
        .lte("date", end_date) \
        .execute()

    title = "Неизвестный SKU"
    diagnostics = []

    # Анализ маржи
    if margin_resp.data:
        df = pd.DataFrame(margin_resp.data)
        df['date'] = pd.to_datetime(df['date'])
        title = df['title'].iloc[0] if df['title'].iloc[0] else str(nmid)

        early = df[df['date'] < mid_date]
        late = df[df['date'] >= mid_date]

        if len(early) > 0 and len(late) > 0:
            e_margin = early['margin_profit_after_ads'].mean()
            l_margin = late['margin_profit_after_ads'].mean()
            e_ad = early['ad_spend'].mean()
            l_ad = late['ad_spend'].mean()

            if e_margin != 0:
                margin_change = ((l_margin - e_margin) / abs(e_margin)) * 100
                if abs(margin_change) > 20:
                    direction = "📈 выросла" if margin_change > 0 else "📉 упала"
                    diagnostics.append(f"Маржа {direction} на {abs(margin_change):.0f}% ({e_margin:,.0f} → {l_margin:,.0f} ₽/день)")

            if e_ad != 0:
                ad_change = ((l_ad - e_ad) / e_ad) * 100
                if abs(ad_change) > 30:
                    direction = "вырос" if ad_change > 0 else "снизился"
                    diagnostics.append(f"Расход на рекламу {direction} на {abs(ad_change):.0f}%")

    # Анализ воронки
    if funnel_resp.data:
        df = pd.DataFrame(funnel_resp.data)
        df['reportdate'] = pd.to_datetime(df['reportdate'])

        early = df[df['reportdate'] < mid_date]
        late = df[df['reportdate'] >= mid_date]

        if len(early) > 0 and len(late) > 0:
            e_views = early['opencount'].mean()
            l_views = late['opencount'].mean()
            e_orders = early['ordercount'].mean()
            l_orders = late['ordercount'].mean()

            if e_views != 0:
                views_change = ((l_views - e_views) / e_views) * 100
                if abs(views_change) > 30:
                    direction = "вырос" if views_change > 0 else "упал"
                    diagnostics.append(f"Трафик {direction} на {abs(views_change):.0f}%")

            e_cr = (e_orders / e_views * 100) if e_views > 0 else 0
            l_cr = (l_orders / l_views * 100) if l_views > 0 else 0

            if abs(l_cr - e_cr) > 1:
                direction = "выросла" if l_cr > e_cr else "упала"
                diagnostics.append(f"Конверсия {direction}: {e_cr:.2f}% → {l_cr:.2f}%")

            # Остатки
            last_stock = late['stocks'].iloc[-1] if 'stocks' in late.columns else None
            if last_stock is not None and last_stock < 50:
                diagnostics.append(f"⚠️ Низкий остаток: {last_stock} шт")

    # Анализ цен
    if price_resp.data:
        df = pd.DataFrame(price_resp.data)
        df['date'] = pd.to_datetime(df['date'])

        early = df[df['date'] < mid_date]
        late = df[df['date'] >= mid_date]

        if len(early) > 0 and len(late) > 0:
            e_price = early['finished_price'].mean()
            l_price = late['finished_price'].mean()

            if e_price != 0:
                price_change = ((l_price - e_price) / e_price) * 100
                if abs(price_change) > 5:
                    direction = "выросла" if price_change > 0 else "снизилась"
                    diagnostics.append(f"Цена {direction} на {abs(price_change):.1f}% ({e_price:,.0f} → {l_price:,.0f} ₽)")

    # Формируем результат
    result = f"""Диагностика SKU: {title}
nmid: {nmid}
Период анализа: {days * 2} дней (сравнение первой и второй половины)

"""

    if diagnostics:
        result += "🔍 Выявленные изменения:\n\n"
        for d in diagnostics:
            result += f"• {d}\n"
    else:
        result += "✅ Значительных изменений не выявлено"

    return result


if __name__ == "__main__":
    print("=== Сравнение периодов ===")
    print(compare_periods.invoke({
        "period1_start": "2026-01-06",
        "period1_end": "2026-01-12",
        "period2_start": "2026-01-13",
        "period2_end": "2026-01-18"
    }))

    print("\n=== Анализ изменений маржи ===")
    print(analyze_margin_change.invoke({"days_back": 7}))

    print("\n=== Аномалии ===")
    print(find_margin_anomalies.invoke({"days": 7}))
