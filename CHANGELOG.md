# 📝 CHANGELOG

Все значимые изменения в проекте документируются в этом файле.

---

## [2.0.1] - 2026-01-03

### Добавлено

#### Must-Match кейсы
- **MM_COM_002** (P1) — Некорректное поведение курьера при общении
  - Триггеры: "обсуждал меня", "смеялся", "комментировал"
  - Тег: Коммуникация с покупателем
  - Ответственный: Курьер

#### Golden Set кейсы
- **GS_PAY_003** — Курьер сам вернул деньги покупателю
  - Маршрут: `route_to_curator`
  - Тег: Оплата / терминал
  
- **GS_HL_002** — Можно ли закрыть заказ без кода?
  - Маршрут: `conditional`
  - Тег: Оплата / гиперссылка
  - Флаг риска: `true`
  
- **GS_HL_003** — Покупатель оплатил, но кода нет
  - Маршрут: `auto_answer`
  - Тег: Оплата / гиперссылка
  
- **GS_013** — Курьер стоял спиной при передаче
  - Маршрут: `auto_answer`
  - Тег: Коммуникация с покупателем
  
- **GS_014** — Покупатель говорит, что оплатил, но подтверждения нет
  - Маршрут: `confidence_routing`
  - Действие: `route_to_support`
  - Тег: Оплата / терминал

### Изменено

- Обновлена статистика в документации:
  - `STATUS.md` — добавлена информация о новых кейсах
  - `IMPLEMENTATION_COMPLETE.md` — обновлена статистика

### Документация

- Создан `docs/CORE_POLICY_UPDATES.md` — описание всех обновлений Core Policy JSON

---

## [2.0.0] - 2026-01-01

### Добавлено

#### Новая архитектура
- **DecisionEngine** — движок принятия решений с улучшенной must-match проверкой
- **ResponseValidator** — валидатор ответов перед отправкой
- **ExplainabilityLogger** — структурированное логирование всех решений
- **NewCuratorService** — новый куратор, интегрирующий все компоненты
- **Core Policy JSON** — единый источник истины для всех правил и кейсов

#### Core Policy JSON
- 14 must-match кейсов (4 P0, 10 P1)
- 23 кейса Golden Set
- 4 основных правила
- 8 тегов

#### Тесты
- Автотесты по Golden Set (`tests/test_golden_set.py`)
- Скрипт проверки работоспособности (`scripts/verify_new_architecture.py`)

#### Скрипты
- `scripts/extract_all_data.py` — извлечение данных из всех источников
- `scripts/sync_to_core_policy.py` — синхронизация данных в Core Policy JSON

#### Документация
- `docs/AUDIT_REPORT.md` — отчет по аудиту
- `docs/EXTRACTION_REPORT.md` — отчет по извлечению данных
- `docs/MODEL_REPORT.md` — описание новой модели
- `docs/REWRITE_REPORT.md` — отчет по переписыванию
- `docs/FINAL_REPORT.md` — финальный отчет
- `docs/QUICK_START_NEW_ARCHITECTURE.md` — быстрый старт
- `docs/ARCHITECTURE_COMPARISON.md` — сравнение архитектур
- `README_NEW_ARCHITECTURE.md` — краткая сводка
- `MIGRATION_SUMMARY.md` — сводка по миграции
- `COMPLETION_CHECKLIST.md` — чеклист завершения
- `STATUS.md` — текущий статус проекта
- `IMPLEMENTATION_COMPLETE.md` — финальная сводка

### Изменено

- `src/handlers/courier_ai.py` — обновлен для использования `NewCuratorService`
- `src/utils/core_policy_loader.py` — новый загрузчик Core Policy JSON

### Улучшено

- Must-match проверка: теперь использует score-based подход вместо строгого совпадения всех триггеров
- Confidence routing: реальный расчет confidence score с учетом 4 факторов
- Валидация ответов: проверка обязательных блоков, тега, forbidden content
- Explainability: все решения логируются в структурированном виде (JSONL)

---

**Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)**
