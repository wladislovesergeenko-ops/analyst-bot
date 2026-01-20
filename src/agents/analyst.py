# src/agents/analyst.py
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from src.config import OPENAI_API_KEY
from src.tools.analytics import get_daily_summary, get_top_sku, get_unprofitable_sku
from src.tools.ads import get_ads_summary, get_high_drr_campaigns, get_scalable_campaigns, get_ads_trend, compare_ads_periods# Собираем tools


tools = [
    # Аналитика
    get_daily_summary,
    get_top_sku,
    get_unprofitable_sku,
    # Реклама
    get_ads_summary,
    get_high_drr_campaigns,
    get_scalable_campaigns,
    get_ads_trend,  # ← новый
    compare_ads_periods
]

# Создаём LLM
llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    api_key=OPENAI_API_KEY,
    temperature=0.2
)

# Системный промпт
system_prompt = f"""Ты аналитик e-commerce компании, продающей БАДы и витамины на Wildberries.

Твои задачи:
1. Отвечать на вопросы о продажах, марже и эффективности артикулов
2. Анализировать рекламные кампании и давать рекомендации

Правила для рекламы:
- ДРР > 15% — кампания требует оптимизации
- ДРР < 15% и CR > 8% — кампанию можно масштабировать

ВАЖНО про зависимость от рекламы:
- Если доля рекламной выручки > 50% — оптимизация должна быть КОНСЕРВАТИВНОЙ
- Резкое снижение ставок может обрушить продажи
- В таких случаях рекомендуй снижать ставки на 10-15%, не более
- Если доля < 30% — можно оптимизировать агрессивнее

Отвечай на русском языке, кратко и по делу.

Сегодня: {datetime.now().strftime("%Y-%m-%d")}
Вчера: {(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")}
"""

# Создаём агента ← ЭТО ОТСУТСТВОВАЛО
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=system_prompt
)

if __name__ == "__main__":
    # Тест агента
    test_questions = [
        "Как вчера отработала компания?",
        "Как вчера отработала реклама?",
        "Выведи сравнение по неделям для рекламы.",
        "Какие артикулы вчера принесли наибольшую маржу?",
        "Какие артикулы вчера были убыточными?",
        "Какие рекламные кампании требуют оптимизации?",
    ]
    
    for question in test_questions:
        print(f"\n{'='*50}")
        print(f"Вопрос: {question}")
        print(f"{'='*50}")
        
        response = agent.invoke({"messages": [{"role": "user", "content": question}]})
        
        print(response["messages"][-1].content)