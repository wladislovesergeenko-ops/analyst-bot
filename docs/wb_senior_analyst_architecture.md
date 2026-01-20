# Senior WB Analyst Agent — Архитектура

## 1. Обзор

**Цель:** AI-агент уровня Senior Data Analyst для Wildberries, отвечающий на главный вопрос бизнеса — **"Как и за счёт чего увеличить прибыль?"**

**LLM:** GPT-4o-mini
**Оркестрация:** LangGraph
**БД:** Supabase (PostgreSQL)

---

## 2. Схема данных WB

```
┌─────────────────────────────────────────────────────────────────┐
│                        ДАННЫЕ WB                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  wb_unit_economics          wb_sales_plan                       │
│  ┌─────────────┐           ┌─────────────┐                      │
│  │ nm_id (PK)  │           │ nmid        │                      │
│  │ purchase_   │           │ month       │                      │
│  │   price     │           │ plan_margin │                      │
│  │ commission  │           │ plan_orders │                      │
│  │ logistics   │           └──────┬──────┘                      │
│  └──────┬──────┘                  │                             │
│         │                         │                             │
│         ▼                         ▼                             │
│  ┌──────────────────────────────────────┐                       │
│  │        wb_margin_daily (VIEW)        │◄─── Готовый финрез    │
│  │  date, nmid, revenue, ad_spend,      │                       │
│  │  margin_profit_after_ads             │                       │
│  └──────────────────┬───────────────────┘                       │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────┐                       │
│  │      v_plan_fact_margin (VIEW)       │◄─── План/Факт         │
│  │  nmid, plan_margin, fact_margin,     │                       │
│  │  plan_completion_percent             │                       │
│  └──────────────────────────────────────┘                       │
│                                                                 │
│  wb_sales_funnel_products       v_ads_daily_performance         │
│  ┌─────────────────┐           ┌─────────────────┐              │
│  │ nmid, date      │           │ date, campaign  │              │
│  │ stocks          │           │ ad_spend, drr   │              │
│  │ opencount       │           │ orders, cr      │              │
│  │ cartcount       │           │ clicks, ctr     │              │
│  │ ordercount      │           └─────────────────┘              │
│  │ buyoutcount     │                                            │
│  └─────────────────┘           wb_spp_daily                     │
│                                ┌─────────────────┐              │
│                                │ date, nmid      │              │
│                                │ spp, price      │              │
│                                └─────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Архитектура LangGraph

### 3.1 Граф агента

```
                    ┌─────────────────┐
                    │  User Question  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ classify_intent │  ← Определяет тип вопроса
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
       ┌──────────┐   ┌──────────┐   ┌──────────┐
       │ describe │   │ diagnose │   │ prescribe│
       │  (Tier1) │   │  (Tier2) │   │ (Tier4)  │
       └────┬─────┘   └────┬─────┘   └────┬─────┘
            │              │              │
            └──────────────┼──────────────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │    synthesize   │  ← Собирает ответ
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     Response    │
                    └─────────────────┘
```

### 3.2 State (типизированный)

```python
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph

class AnalystState(TypedDict):
    # Input
    question: str

    # Intent classification
    intent: Literal["describe", "diagnose", "prescribe", "clarify"]
    entities: dict  # {sku: [...], date_range: {...}, metrics: [...]}

    # Analysis results
    data_context: dict      # Результаты SQL-запросов
    insights: list[str]     # Найденные инсайты
    recommendations: list[dict]  # Приоритизированные рекомендации

    # Output
    response: str

    # Memory
    conversation_history: list[dict]
```

### 3.3 Nodes

#### `classify_intent`
Определяет тип вопроса и извлекает сущности.

```python
def classify_intent(state: AnalystState) -> AnalystState:
    """
    Классифицирует вопрос:
    - describe: "Какая маржа за вчера?", "Топ-5 по прибыли"
    - diagnose: "Почему упала маржа?", "Что случилось с SKU X?"
    - prescribe: "Что делать?", "Какие SKU оптимизировать?"
    - clarify: Недостаточно информации для ответа

    Извлекает:
    - SKU (nmid или название)
    - Период (вчера, неделя, месяц, конкретные даты)
    - Метрики (маржа, выручка, ДРР, заказы)
    """
```

#### `describe` (Tier 1)
Descriptive analytics — факты по данным.

```python
def describe(state: AnalystState) -> AnalystState:
    """
    Tools:
    - get_margin_summary(date) — сводка по марже
    - get_plan_fact() — выполнение плана
    - get_top_sku(metric, n) — топ по метрике
    - get_funnel_summary(date) — воронка продаж
    - get_ads_summary(date) — сводка по рекламе
    """
```

#### `diagnose` (Tier 2)
Diagnostic analytics — почему произошло.

```python
def diagnose(state: AnalystState) -> AnalystState:
    """
    Tools:
    - compare_periods(period1, period2) — сравнение периодов
    - decompose_margin_change(period1, period2) — декомпозиция изменения маржи
    - find_anomalies(metric, days) — поиск аномалий
    - analyze_sku_decline(nmid) — диагностика падения SKU
    """
```

#### `prescribe` (Tier 4)
Prescriptive analytics — что делать.

```python
def prescribe(state: AnalystState) -> AnalystState:
    """
    Tools:
    - get_optimization_candidates() — SKU для оптимизации
    - get_underperformers() — отстающие от плана
    - get_ads_optimization() — рекомендации по рекламе
    - prioritize_actions() — приоритизация по impact
    """
```

#### `synthesize`
Формирует финальный ответ.

```python
def synthesize(state: AnalystState) -> AnalystState:
    """
    Собирает данные из предыдущих нод.
    Формирует структурированный ответ:
    - Краткий вывод (1-2 предложения)
    - Детали (таблицы, цифры)
    - Рекомендации (если prescribe)
    """
```

### 3.4 Routing

```python
def route_by_intent(state: AnalystState) -> str:
    intent = state["intent"]

    if intent == "describe":
        return "describe"
    elif intent == "diagnose":
        return ["describe", "diagnose"]  # Сначала факты, потом анализ
    elif intent == "prescribe":
        return ["describe", "diagnose", "prescribe"]  # Полный цикл
    else:
        return "clarify"
```

---

## 4. Tools по уровням

### Tier 1: Descriptive (MVP)

| Tool | Параметры | SQL-логика |
|------|-----------|------------|
| `get_margin_summary` | date | SUM(margin_profit_after_ads) FROM wb_margin_daily |
| `get_plan_fact` | - | SELECT * FROM v_plan_fact_margin |
| `get_top_sku` | metric, n, date | ORDER BY metric DESC LIMIT n |
| `get_bottom_sku` | metric, n, date | ORDER BY metric ASC LIMIT n |
| `get_funnel_summary` | date | SUM(opencount, cartcount, ordercount) FROM wb_sales_funnel |
| `get_ads_summary` | date | SUM(ad_spend, orders, revenue), AVG(drr) FROM v_ads |
| `get_stock_alerts` | threshold | WHERE stocks < threshold |

### Tier 2: Diagnostic (v1)

| Tool | Параметры | Логика |
|------|-----------|--------|
| `compare_periods` | period1, period2 | Δ по всем метрикам между периодами |
| `decompose_margin_change` | period1, period2 | Price effect + Volume effect + Mix effect |
| `find_anomalies` | metric, days | Z-score > 2 или < -2 |
| `analyze_sku_decline` | nmid | Проверка: цена? трафик? конверсия? реклама? остатки? |
| `get_conversion_changes` | period1, period2 | Δ CR на каждом этапе воронки |

### Tier 3: Predictive (v2)

| Tool | Параметры | Логика |
|------|-----------|--------|
| `forecast_demand` | nmid, days | Prophet / экспоненциальное сглаживание |
| `forecast_month_margin` | - | Экстраполяция текущего темпа |
| `predict_stockout` | nmid | Текущий stock / avg daily sales |

### Tier 4: Prescriptive (v1)

| Tool | Параметры | Логика |
|------|-----------|--------|
| `get_optimization_candidates` | - | ДРР > 20% AND ad_spend > X |
| `get_underperformers` | - | plan_completion < 80% |
| `get_scaling_candidates` | - | ДРР < 10% AND CR > 8% |
| `get_price_opportunities` | - | Маржа > 40% AND конкуренты дороже |
| `prioritize_actions` | actions | Сортировка по impact * feasibility |

---

## 5. System Prompt

```
Ты Senior Data Analyst e-commerce компании, продающей БАДы и витамины на Wildberries.

## Твоя роль
Отвечать на аналитические вопросы и помогать увеличивать прибыль компании.

## Данные, к которым у тебя есть доступ
- wb_margin_daily: ежедневная маржа по SKU (готовый финрез)
- v_plan_fact_margin: план/факт по марже с % выполнения
- wb_sales_funnel_products: воронка продаж (просмотры → корзина → заказы → выкупы) + остатки
- v_ads_daily_performance: эффективность рекламы (расход, ДРР, CR, CTR)
- wb_spp_daily: цены с учётом СПП
- wb_unit_economics: себестоимость и комиссии

## Бизнес-контекст
- ~100 SKU активных
- Целевая маржинальность: 18%+
- ДРР > 15% — требует оптимизации
- ДРР < 10% при CR > 8% — можно масштабировать

## Как отвечать

### На описательные вопросы ("какая маржа?", "топ SKU")
1. Дай конкретные цифры
2. Сравни с планом или прошлым периодом
3. Выдели аномалии

### На диагностические вопросы ("почему упало?")
1. Сначала покажи факт изменения
2. Проверь возможные причины по порядку:
   - Цена изменилась?
   - Трафик упал?
   - Конверсия снизилась?
   - Реклама стала дороже?
   - Закончились остатки?
3. Укажи наиболее вероятную причину

### На вопросы "что делать?"
1. Дай 3-5 конкретных рекомендаций
2. Приоритизируй по влиянию на прибыль
3. Укажи ожидаемый эффект в рублях где возможно

## Формат ответа
- Начни с краткого вывода (1-2 предложения)
- Затем детали с цифрами
- Используй таблицы для сравнений
- Завершай рекомендацией если уместно

## Ограничения
- Не выдумывай данные — используй только tools
- Если данных недостаточно — скажи об этом
- Не давай финансовых советов вне своей компетенции

Сегодня: {current_date}
```

---

## 6. Примеры диалогов

### Пример 1: Описательный вопрос

**User:** Как выполняется план по марже в этом месяце?

**Agent:**
```
План по марже выполняется на 87% от линейного графика.

| Показатель | План на сегодня | Факт | Δ |
|------------|-----------------|------|---|
| Маржа | 1,245,000 ₽ | 1,083,150 ₽ | -13% |

Топ-3 отстающих от плана:
1. Коллаген порошок — 62% плана (-156K ₽)
2. Омега-3 — 71% плана (-89K ₽)
3. Витамин D3 — 78% плана (-45K ₽)

Рекомендация: Сфокусироваться на Коллагене — наибольший потенциал дозагрузки.
```

### Пример 2: Диагностический вопрос

**User:** Почему вчера упала маржа?

**Agent:**
```
Маржа вчера: 42,300 ₽ (на 28% ниже среднего за неделю).

Диагностика:
✗ Цены — без изменений
✗ Трафик — +5% к среднему
✓ Конверсия — упала с 4.2% до 2.8% (-33%)
✗ Реклама — ДРР в норме (12%)
✗ Остатки — в наличии

Причина: Падение конверсии.

Детализация по SKU с наибольшим падением CR:
| SKU | CR было | CR стало | Потеря заказов |
|-----|---------|----------|----------------|
| Коллаген | 5.1% | 2.3% | -12 заказов |
| L-карнитин | 3.8% | 2.1% | -8 заказов |

Гипотеза: Проверь карточки этих товаров — возможно появились негативные отзывы или конкуренты снизили цены.
```

### Пример 3: Prescriptive вопрос

**User:** Какие SKU нужно оптимизировать в первую очередь?

**Agent:**
```
Топ-5 SKU для оптимизации по влиянию на прибыль:

| # | SKU | Проблема | Действие | Ожидаемый эффект |
|---|-----|----------|----------|------------------|
| 1 | Коллаген порошок | ДРР 24% | Снизить ставку с 85₽ до 65₽ | +45K ₽/мес |
| 2 | 5-HTP | Отставание от плана 38% | Увеличить бюджет рекламы | +67K ₽/мес |
| 3 | Омега-3 комплекс | Низкий CR 1.8% | Оптимизировать карточку | +32K ₽/мес |
| 4 | Витамин B12 | Остаток 12 дней | Заказать поставку | Избежать -28K ₽ |
| 5 | Магний B6 | ДРР 31% | Снизить ставку или стоп | +18K ₽/мес |

Суммарный потенциал: +190K ₽/месяц

Начни с #1 (Коллаген) — максимальный эффект при минимальном риске.
```

---

## 7. План разработки

### MVP (2 недели)

**Цель:** Агент отвечает на базовые вопросы по данным.

**Неделя 1:**
- [ ] Настроить LangGraph с базовым графом
- [ ] Реализовать classify_intent (пока rule-based)
- [ ] Tier 1 tools: get_margin_summary, get_plan_fact, get_top_sku
- [ ] Базовый system prompt
- [ ] Тесты на 10 вопросов

**Неделя 2:**
- [ ] Tier 1 tools: get_funnel_summary, get_ads_summary, get_stock_alerts
- [ ] Улучшить classify_intent (LLM-based)
- [ ] Добавить synthesize node
- [ ] CLI интерфейс для тестирования
- [ ] Документация

**Deliverable:** Агент отвечает на вопросы типа "какая маржа?", "топ SKU", "выполнение плана".

---

### v1.0 (+ 2 недели)

**Цель:** Диагностика + базовые рекомендации.

**Неделя 3:**
- [ ] Tier 2 tools: compare_periods, find_anomalies
- [ ] Tier 2 tools: analyze_sku_decline
- [ ] Реализовать diagnose node

**Неделя 4:**
- [ ] Tier 4 tools: get_optimization_candidates, get_underperformers
- [ ] Реализовать prescribe node
- [ ] Memory через SQLite checkpointer
- [ ] Улучшить synthesize (таблицы, форматирование)

**Deliverable:** Агент отвечает "почему упало" и "что делать".

---

### v2.0 (+ 2-3 недели)

**Цель:** Прогнозы + продвинутая аналитика.

- [ ] Tier 3 tools: forecast_demand, forecast_month_margin
- [ ] decompose_margin_change (price/volume/mix effect)
- [ ] Интеграция с Telegram ботом
- [ ] Автоматические алерты (план < 80%, ДРР > 25%)
- [ ] Human-in-the-loop для рискованных рекомендаций

---

## 8. Структура файлов

```
src/
├── agents/
│   └── wb_senior_analyst.py    # Главный агент
├── graph/
│   ├── state.py                # AnalystState
│   ├── nodes/
│   │   ├── classify.py         # classify_intent
│   │   ├── describe.py         # describe node
│   │   ├── diagnose.py         # diagnose node
│   │   ├── prescribe.py        # prescribe node
│   │   └── synthesize.py       # synthesize node
│   └── graph.py                # LangGraph сборка
├── tools/
│   ├── wb_margin.py            # Tools для маржи
│   ├── wb_funnel.py            # Tools для воронки
│   ├── wb_ads.py               # Tools для рекламы (уже есть)
│   ├── wb_plan.py              # Tools для плана
│   └── wb_diagnostics.py       # Tools для диагностики
└── prompts/
    └── senior_analyst.py       # System prompt
```

---

## 9. Метрики успеха

| Метрика | MVP | v1.0 | v2.0 |
|---------|-----|------|------|
| Покрытие вопросов | 60% | 85% | 95% |
| Точность ответов | 80% | 90% | 95% |
| Время ответа | <10s | <15s | <20s |
| Полезность рекомендаций | - | 70% | 85% |

---

## 10. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| LLM галлюцинирует данные | Высокая | Все цифры только из tools, валидация |
| Медленные запросы к БД | Средняя | Индексы, кэширование, материализованные views |
| Неправильная классификация intent | Средняя | Few-shot примеры, fallback на clarify |
| Слишком общие рекомендации | Средняя | Требовать конкретные цифры в промпте |
