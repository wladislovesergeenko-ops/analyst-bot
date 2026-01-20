# src/agents/ozon_analyst.py

from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from src.config import OPENAI_API_KEY
from src.tools.ozon_analytics import (
    get_ozon_daily_summary,
    get_ozon_top_sku,
    get_ozon_conversion_funnel,
    get_ozon_low_conversion_sku
)
from src.tools.ozon_ads import (
    get_ozon_ads_summary,
    get_ozon_high_drr_campaigns,
    get_ozon_scalable_campaigns,
    get_ozon_ads_trend,
    get_ozon_campaign_details
)

# Собираем tools
tools = [
    # Аналитика продаж
    get_ozon_daily_summary,
    get_ozon_top_sku,
    get_ozon_conversion_funnel,
    get_ozon_low_conversion_sku,
    # Реклама
    get_ozon_ads_summary,
    get_ozon_high_drr_campaigns,
    get_ozon_scalable_campaigns,
    get_ozon_ads_trend,
    get_ozon_campaign_details
]

# Создаём LLM
llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    api_key=OPENAI_API_KEY,
    temperature=0.2
)

# Системный промпт для Ozon-аналитика
system_prompt = f"""Ты аналитик e-commerce компании, продающей БАДы и витамины на Ozon.

Твои задачи:
1. Отвечать на вопросы о продажах, конверсии и эффективности SKU
2. Анализировать рекламные кампании и давать рекомендации
3. Находить точки роста через анализ воронки конверсии

Ключевые метрики Ozon:
- Просмотры (hits_view) — общее количество просмотров
- Сессии (session_view) — уникальные посетители
- Конверсия: сессия → заказ — главный показатель эффективности карточки
- Позиция в категории — влияет на органический трафик

Правила для рекламы:
- ДРР > 15% — кампания требует оптимизации
- ДРР < 15% и CR > 5% — кампанию можно масштабировать (порог CR ниже чем на WB)
- Учитывай ассоциированные конверсии (model_orders, model_revenue)

Специфика Ozon:
- Разделяй трафик: поиск vs карточка товара
- Низкая конверсия при высоких просмотрах = проблема с карточкой (фото, описание, цена)
- Позиция в категории важна для органики

Рекомендации по оптимизации:
- CR < 1% при просмотрах > 100 — нужно улучшать карточку
- Много добавлений в корзину, мало заказов — проблема с ценой или доставкой
- ДРР > 30% — срочно снижать ставки или отключать товар

Отвечай на русском языке, кратко и по делу.

Сегодня: {datetime.now().strftime("%Y-%m-%d")}
Вчера: {(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")}
"""

# Создаём агента
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=system_prompt
)

if __name__ == "__main__":
    # Тест агента
    test_questions = [
        "Дай сводку по продажам Ozon за вчера",
        "Покажи воронку конверсии за вчера",
        "Какие SKU имеют низкую конверсию?",
        "Как отработала реклама Ozon вчера?",
        "Какие товары в рекламе требуют оптимизации?",
        "Какие товары можно масштабировать?",
        "Покажи динамику ДРР за неделю",
    ]

    for question in test_questions:
        print(f"\n{'='*50}")
        print(f"Вопрос: {question}")
        print(f"{'='*50}")

        response = agent.invoke({"messages": [{"role": "user", "content": question}]})

        print(response["messages"][-1].content)
