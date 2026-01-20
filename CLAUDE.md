# CLAUDE.md - Контекст проекта для AI-ассистента

## Обзор проекта

**ecom_analytics** — AI-агенты для аналитики e-commerce на маркетплейсах Wildberries и Ozon.

Технологический стек:
- Python 3.13
- LangChain + LangGraph (ReAct агенты)
- OpenAI GPT-4o-mini
- Supabase (PostgreSQL)

## Структура репозитория

```
ecom_analytics/
├── src/
│   ├── agents/
│   │   ├── analyst.py          # ReAct агент для Wildberries
│   │   └── ozon_analyst.py     # ReAct агент для Ozon
│   ├── tools/
│   │   ├── analytics.py        # Tools для аналитики продаж WB
│   │   ├── ads.py              # Tools для анализа рекламы WB
│   │   ├── ozon_analytics.py   # Tools для аналитики продаж Ozon
│   │   └── ozon_ads.py         # Tools для анализа рекламы Ozon
│   ├── db/
│   │   └── supabase.py         # Подключение к Supabase
│   └── config.py               # Загрузка переменных окружения
├── sql/
│   ├── queries/                # SQL запросы
│   └── views/                  # SQL views
├── tests/
│   └── test_tools.py           # Тесты tools
├── experiments/                # Эксперименты и прототипы
├── .env                        # Переменные окружения (не в git)
└── requirements.txt            # Зависимости
```

## Архитектура агентов

Используется **ReAct паттерн** (Reasoning + Acting) через `langgraph.prebuilt.create_react_agent`.

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
```

### Агенты

| Агент | Файл | Маркетплейс | Описание |
|-------|------|-------------|----------|
| WB Analyst | `src/agents/analyst.py` | Wildberries | Аналитика продаж и рекламы WB |
| Ozon Analyst | `src/agents/ozon_analyst.py` | Ozon | Аналитика продаж и рекламы Ozon |

---

## Wildberries Tools

### Аналитика продаж (src/tools/analytics.py)

| Tool | Параметры | Описание |
|------|-----------|----------|
| `get_daily_summary` | date: str | Сводка по всем артикулам за день (выручка, заказы, расход, маржа) |
| `get_top_sku` | date, metric, n | Топ-N артикулов по метрике (margin_profit_after_ads, revenue_total, ordercount) |
| `get_unprofitable_sku` | date, threshold | Артикулы с маржинальностью ниже порога |

### Анализ рекламы WB (src/tools/ads.py)

| Tool | Параметры | Описание |
|------|-----------|----------|
| `get_ads_summary` | date: str | Общая сводка по рекламе (расход, заказы, выручка, ДРР) |
| `get_high_drr_campaigns` | date, threshold | Кампании с высоким ДРР (требуют оптимизации) |
| `get_scalable_campaigns` | date | Кампании для масштабирования (CR > 8%, ДРР < 15%) |
| `get_ads_trend` | metric, days | Динамика метрики за N дней |
| `compare_ads_periods` | period1_start, period1_end, period2_start, period2_end | Сравнение двух периодов |

---

## Ozon Tools

### Аналитика продаж (src/tools/ozon_analytics.py)

| Tool | Параметры | Описание |
|------|-----------|----------|
| `get_ozon_daily_summary` | date: str | Сводка по всем SKU за день (выручка, заказы, доставки, просмотры, конверсия) |
| `get_ozon_top_sku` | date, metric, n | Топ-N SKU по метрике (revenue, ordered_units, hits_view, session_view) |
| `get_ozon_conversion_funnel` | date | Воронка: просмотры → корзина → заказы (с CR на каждом этапе) |
| `get_ozon_low_conversion_sku` | date, min_views, max_cr | SKU с низкой конверсией — кандидаты на оптимизацию карточки |

### Анализ рекламы Ozon (src/tools/ozon_ads.py)

| Tool | Параметры | Описание |
|------|-----------|----------|
| `get_ozon_ads_summary` | date: str | Общая сводка по рекламе (расход, заказы с ассоциированными, выручка, ДРР) |
| `get_ozon_high_drr_campaigns` | date, threshold | Товары с высоким ДРР (требуют оптимизации) |
| `get_ozon_scalable_campaigns` | date, max_drr, min_cr | Товары для масштабирования (ДРР < 15%, CR > 5%) |
| `get_ozon_ads_trend` | metric, days | Динамика метрики за N дней |
| `get_ozon_campaign_details` | campaign_id, date | Детальная статистика по кампании |

---

## База данных (Supabase)

### Таблицы Wildberries

**wb_margin_daily** — ежедневная маржинальность артикулов:
- date, nmid, title, ordercount, revenue_total, ad_spend, margin_profit_after_ads, margin_percent_after_ads

**v_ads_daily_performance** — производительность рекламных кампаний:
- date, campaign_name, ad_spend, ad_revenue, orders, drr, cr, views, clicks, ctr, cpc, bid_search_rub, bid_recommendations_rub, ad_revenue_share, is_scalable

### Таблицы Ozon

**ozon_analytics_data** — ежедневная аналитика SKU:
- date, sku, product_name, revenue, ordered_units, delivered_units
- hits_view_search, hits_view_pdp, hits_view (просмотры)
- hits_tocart_search, hits_tocart_pdp, hits_tocart (добавления в корзину)
- session_view_search, session_view_pdp, session_view (сессии)
- position_category (позиция в категории)

**ozon_campaign_product_stats** — статистика рекламы по товарам:
- campaign_id, date, sku, product_name, price
- impressions, clicks, ctr, add_to_cart, avg_cpc, cost
- orders, revenue (прямые конверсии)
- model_orders, model_revenue (ассоциированные конверсии)
- drr (ДРР от Ozon, учитывает все конверсии)

---

## Бизнес-правила

### Wildberries
- ДРР > 15% → кампания требует оптимизации
- ДРР < 15% и CR > 8% → кампанию можно масштабировать
- Доля рекламной выручки > 50% → консервативная оптимизация
- Доля рекламной выручки < 30% → агрессивная оптимизация

### Ozon
- ДРР > 15% → кампания требует оптимизации
- ДРР < 15% и CR > 5% → кампанию можно масштабировать (порог CR ниже чем на WB)
- CR < 1% при просмотрах > 100 → нужно улучшать карточку
- Много добавлений в корзину, мало заказов → проблема с ценой или доставкой
- ДРР > 30% → срочно снижать ставки или отключать товар

### Ozon: ассоциированные конверсии
- `orders + model_orders` = общее количество заказов
- `revenue + model_revenue` = общая выручка
- ДРР в таблице уже учитывает ассоциированные конверсии (данные от Ozon)

---

## Конфигурация

Переменные окружения в `.env`:
```
OPENAI_API_KEY=sk-proj-...
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=eyJ...
```

## Команды для разработки

```bash
# Активация виртуального окружения
source venv/bin/activate

# Запуск WB агента
python -m src.agents.analyst

# Запуск Ozon агента
python -m src.agents.ozon_analyst

# Тест подключения к БД
python test.py
```

## Планы развития

### Выполнено
- [x] Интеграция с Ozon (tools для аналитики и рекламы)
- [x] Отдельный агент для Ozon

### В разработке
- [ ] Multi-agent система (оркестратор + специализированные агенты)
- [ ] Расширение tools для WB (остатки, поставки, ABC-анализ)
- [ ] Сравнение периодов для Ozon (compare_ozon_periods)

### Идеи
- Memory для сохранения контекста разговора
- Подключение к live API маркетплейсов
- Telegram/Slack бот интерфейс
- Автоматические отчёты по расписанию
- Кросс-маркетплейсовая аналитика (WB vs Ozon)

## Соглашения по коду

- Tools создаются с декоратором `@tool` из `langchain_core.tools`
- Docstring в tools — описание для LLM (на русском)
- Возвращаемое значение tools — форматированная строка
- Все запросы к БД через `src/db/supabase.py`
- Ozon tools имеют префикс `get_ozon_*` для отличия от WB

## Полезные метрики

| Метрика | Описание | Формула |
|---------|----------|---------|
| ДРР | Доля рекламного расхода | ad_spend / ad_revenue * 100 |
| CR | Конверсия | orders / clicks * 100 |
| CTR | Кликабельность | clicks / views * 100 |
| CPC | Цена клика | ad_spend / clicks |
| ad_revenue_share | Доля рекламной выручки | ad_revenue / revenue_total * 100 |

### Специфичные метрики Ozon

| Метрика | Описание | Формула |
|---------|----------|---------|
| CR просмотр→корзина | Конверсия в корзину | hits_tocart / hits_view * 100 |
| CR сессия→заказ | Конверсия в заказ | ordered_units / session_view * 100 |
| Общие заказы | С ассоциированными | orders + model_orders |
| Общая выручка | С ассоциированной | revenue + model_revenue |
