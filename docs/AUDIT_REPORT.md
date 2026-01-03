# 📊 ОТЧЕТ ПО АУДИТУ СИСТЕМЫ AI-КУРАТОРА

**Дата:** 2026-01-01  
**Статус:** ЭТАП 1 — АУДИТ (завершен)

---

## 🎯 ЦЕЛЬ АУДИТА

Проанализировать текущую реализацию AI-бота для доставки, выявить:
- Источники правил и регламентов
- Логику принятия решений
- Структуру данных
- Проблемы и расхождения с требованиями

---

## 📚 1. ИСТОЧНИКИ ПРАВИЛ И РЕГЛАМЕНТОВ

### 1.1 JSON-конфигурация (ОСНОВНОЙ ИСТОЧНИК)

**Файл:** `src/ai/delivery_curator_config.json` (1387 строк)

**Содержит:**
- ✅ `knowledge_base.rules` — правила доставки (KB_DELIVERY_001, KB_TEMP_001, KB_RETURN_001)
- ✅ `knowledge_base.tags` — теги обращений (8 тегов)
- ✅ `must_match_cases` — обязательные кейсы (MM_001-MM_005, MM_COM_001-MM_COM_002, MM_PAY_001-MM_PAY_002, MM_HL_001-MM_HL_003, MM_RET_P0_001-MM_RET_P0_002)
- ✅ `golden_set` — эталонные кейсы (GS_001-GS_015)
- ✅ `training_cases` — обучающие кейсы (CASE_001-CASE_004)
- ✅ `delivery_codex` — кодекс доставки (версия 5.06.24)
- ✅ `payment_policy` — политика оплаты
- ✅ `returns_policy_v1_1` — политика возвратов (P0)
- ✅ `confidence_routing` — правила маршрутизации
- ✅ `response_structure` — структура ответа
- ✅ `response_validator` — правила валидации ответов
- ✅ `explainability_log_schema` — схема логов объяснимости

**Статус:** ✅ Хорошо структурирован, соответствует требованиям JSON-first архитектуры

---

### 1.2 База данных PostgreSQL

#### Таблица `faq_ai`
- **Назначение:** FAQ записи для RAG
- **Поля:** `id`, `question`, `answer`, `keywords[]`, `category`, `tag`, `search_vector`
- **Миграция:** `migrations/001_create_faq_ai_table.sql`

#### Таблица `unified_knowledge_base`
- **Назначение:** Объединенная база знаний (FAQ + chunks из PDF)
- **Поля:** `type` ('faq' | 'chunk'), `question`, `answer`, `keywords[]`, `category`, `tag`, `source`, `chunk_index`, `content`, `search_vector`
- **Миграция:** `migrations/009_create_unified_knowledge_base.sql`
- **Статус:** ⚠️ Дублирование с `faq_ai` (нужна миграция)

#### Таблица `ml_cases`
- **Назначение:** ML-кейсы для обучения и explainability
- **Поля:** `id`, `input`, `label`, `decision`, `explanation`, `input_vector`, `explanation_vector`
- **Миграция:** `migrations/004_create_ml_cases_table.sql`
- **Файл данных:** `ml_cases.jsonl` (51 кейс)

**Статус:** ⚠️ Есть дублирование между таблицами и JSON-конфигом

---

### 1.3 Файлы данных

- `ml_cases.jsonl` — 51 кейс для обучения классификатора
- `docs/Data.pdf` — PDF с регламентами (118512 строк)

**Статус:** ✅ Данные есть, но не все используются

---

## 🔍 2. ЛОГИКА ПРИНЯТИЯ РЕШЕНИЙ

### 2.1 Основной класс: `AICurator`

**Файл:** `src/ai/curator.py` (844 строки)

**Текущая логика:**

```python
async def generate_response(user_id, question, prompt_type="question"):
    1. Если prompt_type == "warning" или "broadcast" → генерируем без routing
    2. Проверяем must-match кейсы через check_must_match_case(question)
    3. Если найден must-match → генерируем ответ с must-match контекстом
    4. Иначе ищем FAQ через _get_faqs_for_question(question)
    5. Если FAQ нет → эскалация к куратору
    6. Если FAQ есть → генерируем ответ через Groq API
```

**Проблемы:**
- ❌ **Must-match проверка слишком простая:** `all(trigger in question_lower for trigger in triggers)` — требует ВСЕ триггеры одновременно
- ❌ **Confidence routing не реализован:** только проверка наличия FAQ (есть/нет)
- ❌ **Нет реального confidence score:** нет расчета вероятности совпадения
- ❌ **Нет explainability logs:** решения не логируются в структурированном виде
- ❌ **Нет валидации ответа:** структура ответа не проверяется перед отправкой

---

### 2.2 Must-Match проверка

**Файл:** `src/utils/config_loader.py`, функция `check_must_match_case()`

**Текущая логика:**
```python
def check_must_match_case(question: str) -> Optional[Dict[str, Any]]:
    question_lower = question.lower()
    must_match_cases = get_must_match_cases()
    
    for case in must_match_cases:
        triggers = case.get("trigger", [])
        # Проверяем, содержатся ли ВСЕ триггеры в вопросе
        if all(trigger.lower() in question_lower for trigger in triggers):
            return case
    
    return None
```

**Проблемы:**
- ❌ Требует ВСЕ триггеры одновременно (слишком строго)
- ❌ Нет семантического поиска (только точное совпадение подстрок)
- ❌ Нет приоритетов (P0/P1/P2)
- ❌ Нет threshold (0.8 указан в конфиге, но не используется)

**Пример проблемы:**
- Кейс MM_001: `trigger: ["яйца разбиты", "упаковка целая", "разбилось при доставке"]`
- Вопрос: "Яйца разбиты, упаковка целая" → **НЕ совпадет** (нет "разбилось при доставке")

---

### 2.3 Confidence Routing

**Текущая реализация:**
```python
# Простая проверка confidence: если есть релевантные FAQ, отвечаем
if not faqs or len(faqs) == 0:
    return escalation_message
```

**Проблемы:**
- ❌ Нет расчета confidence score (0.0-1.0)
- ❌ Нет порогов (0.8 для auto_answer, 0.6 для clarification)
- ❌ Нет проверки mandatory escalation triggers
- ❌ Нет уточняющих вопросов

**Что должно быть (из конфига):**
```json
"confidence_score": {
  "thresholds": {
    "auto_answer": 0.8,
    "clarification_required": 0.6,
    "route_to_curator": 0.0
  }
}
```

**Статус:** ❌ Не реализовано

---

### 2.4 Валидация ответа

**Конфиг содержит `response_validator`:**
```json
{
  "required_blocks": ["Суть ситуации", "Кто отвечает", "Почему", "Что делать сейчас"],
  "rules": [
    {"id": "VAL_001", "rule": "Ответ должен содержать все обязательные блоки"},
    {"id": "VAL_002", "rule": "Разрешён только один основной тег"},
    {"id": "VAL_003", "rule": "Запрещены оценки личности и наказания"}
  ]
}
```

**Проблемы:**
- ❌ Валидация НЕ выполняется перед отправкой ответа
- ❌ Нет проверки структуры ответа
- ❌ Нет проверки forbidden content

**Статус:** ❌ Не реализовано

---

### 2.5 Explainability Logs

**Конфиг содержит схему:**
```json
"explainability_log_schema": {
  "fields": {
    "user_query": "string",
    "matched_source": {"type": ["rule", "case", "golden_set", "fallback"], "id": "string"},
    "decision_route": ["auto_answer", "confidence_routing", "route_to_curator"],
    "selected_tag": "string | null",
    "confidence_level": ["high", "medium", "low"],
    "reason": "string"
  }
}
```

**Проблемы:**
- ❌ Логи НЕ создаются в структурированном виде
- ❌ Нет сохранения explainability logs в БД или файл
- ❌ Нет возможности аудита решений

**Статус:** ❌ Не реализовано

---

## 🗄️ 3. СТРУКТУРА ДАННЫХ

### 3.1 Дублирование данных

**Проблема 1: FAQ в двух местах**
- `faq_ai` таблица (старая)
- `unified_knowledge_base` таблица (новая, type='faq')
- **Решение:** Миграция из `faq_ai` в `unified_knowledge_base`

**Проблема 2: Кейсы в двух местах**
- `ml_cases` таблица (51 кейс из JSONL)
- `delivery_curator_config.json` → `training_cases` (4 кейса)
- `delivery_curator_config.json` → `must_match_cases` (15+ кейсов)
- **Решение:** Нормализация в единую структуру

**Проблема 3: Правила в двух местах**
- `delivery_curator_config.json` → `knowledge_base.rules`
- `delivery_curator_config.json` → `courier_rules`
- `delivery_curator_config.json` → `no_contact_and_return_policy`
- **Решение:** Объединение в единую структуру правил

---

### 3.2 Устаревшие данные

- ⚠️ Таблица `faq_ai` — устарела, заменена на `unified_knowledge_base`
- ⚠️ `ml_cases.jsonl` — не синхронизирован с `ml_cases` таблицей
- ⚠️ `docs/Data.pdf` — не импортирован в базу знаний

---

## 🧪 4. ТЕСТИРОВАНИЕ

### 4.1 Golden Set

**Конфиг содержит:** `golden_set` (15 кейсов: GS_001-GS_015)

**Проблемы:**
- ❌ Нет автотестов по Golden Set
- ❌ Нет проверки перед релизом
- ❌ Нет CI/CD интеграции

**Статус:** ❌ Не реализовано

---

### 4.2 Autotest Schema

**Конфиг содержит схему:**
```json
"autotest_schema": {
  "input": "user_question",
  "expected": {
    "decision_route": "string",
    "tag": "string | null",
    "responsibility": "string | null",
    "structure_valid": true
  },
  "fail_conditions": [
    "Отсутствует один из блоков ответа",
    "Выбрано более одного тега",
    "Назначено наказание",
    "Ответ без matched_source"
  ],
  "note": "Любой fail = блок релиза"
}
```

**Проблемы:**
- ❌ Автотесты НЕ написаны
- ❌ Нет проверки fail conditions

**Статус:** ❌ Не реализовано

---

## ⚠️ 5. КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 5.1 P0 (Блокирующие)

1. **Confidence routing не работает**
   - Нет расчета confidence score
   - Нет проверки mandatory escalation triggers
   - Все решения принимаются на основе простой проверки наличия FAQ

2. **Must-match проверка слишком строгая**
   - Требует ВСЕ триггеры одновременно
   - Пропускает валидные кейсы

3. **Нет валидации ответа**
   - Структура ответа не проверяется
   - Может быть отправлен некорректный ответ

4. **Нет explainability logs**
   - Невозможно аудировать решения
   - Нет возможности отладки

---

### 5.2 P1 (Важные)

1. **Дублирование данных**
   - FAQ в двух таблицах
   - Кейсы в разных местах

2. **Нет автотестов**
   - Golden Set не проверяется автоматически
   - Нет защиты от регрессий

3. **Устаревшие данные**
   - Старые таблицы не мигрированы
   - PDF не импортирован

---

## 📋 6. MAPPING: СТАРЫЕ ДАННЫЕ → НОВАЯ СТРУКТУРА

### 6.1 FAQ

```
faq_ai (старая таблица)
  ↓
unified_knowledge_base (type='faq')
  ↓
Core Policy JSON → knowledge_base.rules
```

### 6.2 Кейсы

```
ml_cases (таблица) + ml_cases.jsonl
  ↓
Core Policy JSON → must_match_cases (P0/P1/P2)
  ↓
Core Policy JSON → golden_set (100 кейсов)
```

### 6.3 Правила

```
delivery_curator_config.json → knowledge_base.rules
delivery_curator_config.json → courier_rules
delivery_curator_config.json → no_contact_and_return_policy
  ↓
Core Policy JSON → rules (единая структура)
```

---

## ✅ 7. ВЫВОДЫ

### Что работает хорошо:
- ✅ JSON-конфигурация хорошо структурирована
- ✅ Есть must-match кейсы в конфиге
- ✅ Есть Golden Set в конфиге
- ✅ Есть схема explainability logs в конфиге
- ✅ Есть валидатор ответов в конфиге

### Что нужно исправить:
- ❌ Реализовать confidence routing с реальным расчетом score
- ❌ Улучшить must-match проверку (семантический поиск, приоритеты)
- ❌ Добавить валидацию ответа перед отправкой
- ❌ Реализовать explainability logs
- ❌ Написать автотесты по Golden Set
- ❌ Мигрировать дублирующиеся данные

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

**ЭТАП 2 — ИЗВЛЕЧЕНИЕ:**
1. Извлечь все полезные данные из текущих источников
2. Нормализовать структуру данных
3. Подготовить миграцию в новую модель

**ЭТАП 3 — НОВАЯ МОДЕЛЬ:**
1. Собрать Core Policy JSON
2. Собрать Golden Set (100 кейсов)
3. Собрать Must-Match кейсы (P0/P1/P2)
4. Реализовать Response Validator
5. Реализовать Explainability Logs

---

**Статус:** ✅ АУДИТ ЗАВЕРШЕН  
**Готовность к ЭТАПУ 2:** ✅ ГОТОВО
