# src/tools/wb_recommendations.py

"""
Tier 4: Prescriptive Analytics Tools

Инструменты для рекомендаций — "что делать?"
"""

import pandas as pd
from datetime import datetime, timedelta
from langchain_core.tools import tool
from src.db.supabase import supabase


@tool
def get_optimization_candidates(date: str = None) -> str:
    """
    Найти SKU, требующие оптимизации (высокий ДРР, низкая маржа).

    Args:
        date: Дата для анализа (по умолчанию вчера)

    Returns:
        Список SKU с рекомендациями по оптимизации
    """
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Данные по марже
    margin_resp = supabase.table("wb_margin_daily") \
        .select("nmid, title, margin_profit_after_ads, margin_percent_after_ads, revenue_total, ad_spend") \
        .eq("date", date) \
        .execute()

    # Данные по рекламе
    ads_resp = supabase.table("v_ads_daily_performance") \
        .select("campaign_name, ad_spend, ad_revenue, drr, cr, orders") \
        .eq("date", date) \
        .execute()

    candidates = []

    # SKU с высоким расходом на рекламу и низкой маржей
    if margin_resp.data:
        for row in margin_resp.data:
            ad_spend = row['ad_spend'] or 0
            margin = row['margin_profit_after_ads'] or 0
            margin_pct = row['margin_percent_after_ads'] or 0
            revenue = row['revenue_total'] or 0

            # Условия для оптимизации
            issues = []
            potential_saving = 0

            # Высокий расход на рекламу относительно маржи
            if ad_spend > 0 and revenue > 0:
                ad_share = (ad_spend / revenue) * 100
                if ad_share > 20:
                    issues.append(f"Высокая доля рекламы: {ad_share:.0f}% от выручки")
                    potential_saving = ad_spend * 0.3  # Потенциал снижения на 30%

            # Низкая маржинальность
            if margin_pct < 15 and revenue > 0:
                issues.append(f"Низкая маржинальность: {margin_pct:.1f}%")

            # Убыточный
            if margin < 0:
                issues.append("🔴 УБЫТОЧНЫЙ")
                potential_saving = abs(margin)

            if issues and ad_spend > 100:  # Только если есть расход на рекламу
                candidates.append({
                    'nmid': row['nmid'],
                    'title': row['title'][:30] if row['title'] else str(row['nmid']),
                    'margin': margin,
                    'margin_pct': margin_pct,
                    'ad_spend': ad_spend,
                    'issues': issues,
                    'potential': potential_saving
                })

    if not candidates:
        return f"Нет SKU, требующих срочной оптимизации за {date}"

    # Сортируем по потенциалу
    candidates.sort(key=lambda x: x['potential'], reverse=True)

    result = f"SKU для оптимизации за {date}:\n\n"

    for c in candidates[:10]:
        result += f"• {c['title']}...\n"
        result += f"  Маржа: {c['margin']:,.0f} ₽ ({c['margin_pct']:.1f}%), Реклама: {c['ad_spend']:,.0f} ₽\n"
        for issue in c['issues']:
            result += f"  ⚠️ {issue}\n"
        if c['potential'] > 0:
            result += f"  💡 Потенциал: +{c['potential']:,.0f} ₽\n"
        result += "\n"

    total_potential = sum(c['potential'] for c in candidates[:10])
    result += f"\n📊 Суммарный потенциал оптимизации: {total_potential:,.0f} ₽"

    return result


@tool
def get_scaling_candidates(date: str = None) -> str:
    """
    Найти SKU для масштабирования (низкий ДРР, высокий CR).

    Args:
        date: Дата для анализа (по умолчанию вчера)

    Returns:
        Список SKU, которые можно масштабировать
    """
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Данные по рекламе
    ads_resp = supabase.table("v_ads_daily_performance") \
        .select("*") \
        .eq("date", date) \
        .execute()

    # Данные по марже
    margin_resp = supabase.table("wb_margin_daily") \
        .select("nmid, title, margin_profit_after_ads, margin_percent_after_ads") \
        .eq("date", date) \
        .execute()

    candidates = []

    if ads_resp.data:
        # Фильтруем: ДРР < 15%, CR > 5%, есть заказы
        for row in ads_resp.data:
            drr = row['drr'] or 0
            cr = row['cr'] or 0
            orders = row['orders'] or 0
            ad_spend = row['ad_spend'] or 0

            if drr > 0 and drr < 15 and cr > 5 and orders >= 1:
                # Оцениваем потенциал роста
                # Если увеличить бюджет на 50%, сколько дополнительных заказов
                potential_orders = int(orders * 0.5)
                avg_order_value = (row['ad_revenue'] / orders) if orders > 0 else 0
                potential_revenue = potential_orders * avg_order_value

                candidates.append({
                    'campaign': row['campaign_name'][:35],
                    'drr': drr,
                    'cr': cr,
                    'orders': orders,
                    'ad_spend': ad_spend,
                    'potential_orders': potential_orders,
                    'potential_revenue': potential_revenue,
                    'bid_search': row.get('bid_search_rub', 0) or 0,
                    'bid_rec': row.get('bid_recommendations_rub', 0) or 0
                })

    if not candidates:
        return f"Нет кампаний для масштабирования за {date}"

    # Сортируем по CR
    candidates.sort(key=lambda x: x['cr'], reverse=True)

    result = f"Кампании для масштабирования за {date}:\n"
    result += "(ДРР < 15%, CR > 5%)\n\n"

    for c in candidates[:10]:
        result += f"• {c['campaign']}...\n"
        result += f"  ДРР: {c['drr']:.1f}%, CR: {c['cr']:.1f}%, Заказов: {c['orders']}\n"
        result += f"  Текущий бюджет: {c['ad_spend']:,.0f} ₽\n"
        result += f"  Ставки: поиск {c['bid_search']:.0f} ₽, каталог {c['bid_rec']:.0f} ₽\n"
        result += f"  💡 При +50% бюджета: ~{c['potential_orders']} доп. заказов (+{c['potential_revenue']:,.0f} ₽)\n\n"

    total_potential = sum(c['potential_revenue'] for c in candidates[:10])
    result += f"\n📊 Потенциал роста выручки: +{total_potential:,.0f} ₽"

    return result


@tool
def get_plan_recommendations() -> str:
    """
    Рекомендации по выполнению плана по марже.

    Анализирует отстающие SKU и предлагает действия.

    Returns:
        Приоритизированные рекомендации для выполнения плана
    """
    # План/факт
    plan_resp = supabase.table("v_plan_fact_margin") \
        .select("*") \
        .execute()

    if not plan_resp.data:
        return "Нет данных по плану"

    df = pd.DataFrame(plan_resp.data)

    # Общее выполнение
    total_plan = df["plan_margin_to_date"].sum()
    total_fact = df["fact_margin_profit"].sum()
    gap = total_plan - total_fact

    if gap <= 0:
        return "✅ План выполняется! Отставания нет."

    recommendations = []

    # 1. Отстающие SKU с планом
    df_valid = df[df["plan_margin_to_date"] > 0].copy()
    df_valid["gap"] = df_valid["plan_margin_to_date"] - df_valid["fact_margin_profit"]
    df_valid["completion"] = df_valid["plan_completion_percent"]

    underperformers = df_valid[df_valid["gap"] > 0].nlargest(5, "gap")

    for _, row in underperformers.iterrows():
        title = row['title'][:25] if row['title'] else str(row['nmid'])
        recommendations.append({
            'sku': title,
            'action': f"Дозагрузить план",
            'gap': row['gap'],
            'completion': row['completion'],
            'priority': 'high' if row['gap'] > gap * 0.1 else 'medium'
        })

    # 2. SKU которые перевыполняют — можно ещё усилить
    overperformers = df_valid[df_valid["plan_completion_percent"] > 120].nlargest(3, "fact_margin_profit")

    for _, row in overperformers.iterrows():
        title = row['title'][:25] if row['title'] else str(row['nmid'])
        recommendations.append({
            'sku': title,
            'action': f"Масштабировать (уже {row['completion']:.0f}% плана)",
            'gap': row['fact_margin_profit'] * 0.2,  # Потенциал +20%
            'completion': row['completion'],
            'priority': 'medium'
        })

    # Формируем результат
    result = f"""Рекомендации по выполнению плана:

📊 Общее отставание: {gap:,.0f} ₽
Текущее выполнение: {total_fact / total_plan * 100:.0f}%

🎯 ПРИОРИТЕТНЫЕ ДЕЙСТВИЯ:

"""

    # Сортируем по приоритету и gap
    recommendations.sort(key=lambda x: (0 if x['priority'] == 'high' else 1, -x['gap']))

    for i, rec in enumerate(recommendations, 1):
        priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡"
        result += f"{i}. {priority_emoji} {rec['sku']}\n"
        result += f"   Действие: {rec['action']}\n"
        result += f"   Потенциал: +{rec['gap']:,.0f} ₽\n\n"

    # Общие рекомендации
    result += """
📝 ОБЩИЕ РЕКОМЕНДАЦИИ:
1. Увеличить бюджет на эффективные кампании (ДРР < 15%)
2. Проверить остатки на складе у топовых SKU
3. Оптимизировать убыточные кампании (снизить ставки или стоп)
"""

    return result


@tool
def get_actionable_insights(date: str = None) -> str:
    """
    Получить топ-5 действий для увеличения прибыли прямо сейчас.

    Анализирует все данные и выдаёт приоритизированный список.

    Args:
        date: Дата для анализа (по умолчанию вчера)

    Returns:
        Топ-5 конкретных действий с ожидаемым эффектом
    """
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    actions = []

    # 1. Проверяем высокий ДРР
    ads_resp = supabase.table("v_ads_daily_performance") \
        .select("campaign_name, ad_spend, drr, orders, ad_revenue") \
        .eq("date", date) \
        .gt("drr", 20) \
        .order("ad_spend", desc=True) \
        .limit(5) \
        .execute()

    if ads_resp.data:
        for row in ads_resp.data:
            saving = row['ad_spend'] * 0.3  # 30% экономии при оптимизации
            actions.append({
                'action': f"Снизить ставки в '{row['campaign_name'][:25]}...'",
                'reason': f"ДРР {row['drr']:.0f}% (слишком высокий)",
                'impact': saving,
                'type': 'cost_reduction'
            })

    # 2. Проверяем низкие остатки у прибыльных SKU
    funnel_resp = supabase.table("wb_sales_funnel_products") \
        .select("nmid, title, stocks, ordercount") \
        .eq("reportdate", date) \
        .lt("stocks", 50) \
        .gt("ordercount", 0) \
        .execute()

    if funnel_resp.data:
        for row in funnel_resp.data:
            title = row['title'][:25] if row['title'] else str(row['nmid'])
            # Потенциальные потери — средний заказ * дни до стока
            potential_loss = row['ordercount'] * 1000 * 7  # ~7 дней без товара
            actions.append({
                'action': f"Заказать поставку '{title}...'",
                'reason': f"Остаток {row['stocks']} шт, заказов {row['ordercount']}/день",
                'impact': potential_loss,
                'type': 'prevent_loss'
            })

    # 3. Масштабируемые кампании
    scale_resp = supabase.table("v_ads_daily_performance") \
        .select("campaign_name, ad_spend, drr, cr, orders, ad_revenue") \
        .eq("date", date) \
        .lt("drr", 10) \
        .gt("cr", 8) \
        .order("orders", desc=True) \
        .limit(3) \
        .execute()

    if scale_resp.data:
        for row in scale_resp.data:
            potential_revenue = row['ad_revenue'] * 0.5  # +50% при масштабировании
            actions.append({
                'action': f"Увеличить бюджет '{row['campaign_name'][:25]}...'",
                'reason': f"ДРР {row['drr']:.0f}%, CR {row['cr']:.0f}% (отличные показатели)",
                'impact': potential_revenue,
                'type': 'revenue_growth'
            })

    # 4. План/факт - отстающие
    plan_resp = supabase.table("v_plan_fact_margin") \
        .select("nmid, title, plan_margin_to_date, fact_margin_profit, plan_completion_percent") \
        .lt("plan_completion_percent", 70) \
        .execute()

    if plan_resp.data:
        for row in plan_resp.data[:3]:
            title = row['title'][:25] if row['title'] else str(row['nmid'])
            gap = (row['plan_margin_to_date'] or 0) - (row['fact_margin_profit'] or 0)
            if gap > 0:
                actions.append({
                    'action': f"Усилить продвижение '{title}...'",
                    'reason': f"Выполнение плана {row['plan_completion_percent']:.0f}%",
                    'impact': gap,
                    'type': 'plan_execution'
                })

    if not actions:
        return "✅ Всё оптимально! Критических действий не требуется."

    # Сортируем по impact
    actions.sort(key=lambda x: x['impact'], reverse=True)

    result = f"🎯 ТОП-5 ДЕЙСТВИЙ для увеличения прибыли:\n\n"

    for i, a in enumerate(actions[:5], 1):
        type_emoji = {
            'cost_reduction': '💰',
            'prevent_loss': '⚠️',
            'revenue_growth': '📈',
            'plan_execution': '📋'
        }.get(a['type'], '•')

        result += f"{i}. {type_emoji} {a['action']}\n"
        result += f"   Причина: {a['reason']}\n"
        result += f"   Эффект: ~{a['impact']:,.0f} ₽\n\n"

    total_impact = sum(a['impact'] for a in actions[:5])
    result += f"📊 Суммарный потенциал: {total_impact:,.0f} ₽"

    return result


if __name__ == "__main__":
    print("=== SKU для оптимизации ===")
    print(get_optimization_candidates.invoke({}))

    print("\n=== Кампании для масштабирования ===")
    print(get_scaling_candidates.invoke({}))

    print("\n=== Рекомендации по плану ===")
    print(get_plan_recommendations.invoke({}))

    print("\n=== Топ-5 действий ===")
    print(get_actionable_insights.invoke({}))
