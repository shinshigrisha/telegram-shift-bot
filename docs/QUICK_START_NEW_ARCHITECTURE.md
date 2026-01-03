# 🚀 БЫСТРЫЙ СТАРТ: НОВАЯ АРХИТЕКТУРА

**Версия:** 2.0.0  
**Дата:** 2026-01-01

---

## 📋 ЧТО ИЗМЕНИЛОСЬ

### Новая архитектура

Бот теперь использует **новую архитектуру** с:
- ✅ **DecisionEngine** — умное принятие решений
- ✅ **ResponseValidator** — валидация ответов
- ✅ **ExplainabilityLogger** — логирование всех решений
- ✅ **Core Policy JSON** — единый источник истины

### Обратная совместимость

- ✅ Старые сервисы (`SimpleCuratorService`, `EnhancedCuratorService`) остаются доступными
- ✅ Fallback на старые сервисы при ошибках
- ✅ Существующие handlers работают без изменений

---

## 🔧 ИСПОЛЬЗОВАНИЕ

### Текущая интеграция

Новая архитектура **уже интегрирована** в `src/handlers/courier_ai.py`:

```python
# Используется NewCuratorService по умолчанию
curator = NewCuratorService(faq_repo=faq_repo, log_dir=log_dir)
answer = await curator.get_answer(question, user_id=user_id)
```

### Как это работает

1. **Пользователь задает вопрос** → `courier_ai.py`
2. **NewCuratorService** обрабатывает вопрос:
   - `DecisionEngine` принимает решение
   - `Groq API` генерирует ответ
   - `ResponseValidator` валидирует ответ
   - `ExplainabilityLogger` логирует решение
3. **Ответ отправляется** пользователю

---

## 📊 МОНИТОРИНГ

### Explainability логи

Все решения логируются в: `logs/explainability/`

**Формат:** JSONL (по дням)
- `explainability_2026-01-01.jsonl`
- `explainability_2026-01-02.jsonl`
- ...

**Структура лога:**
```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "user_id": 123,
  "user_query": "Яйца разбиты",
  "matched_source": {
    "type": "must_match_case",
    "id": "MM_001"
  },
  "decision_route": "auto_answer",
  "confidence_score": 0.95,
  "selected_tag": "Неаккуратная доставка",
  "validation_result": {
    "valid": true,
    "errors": [],
    "warnings": []
  }
}
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Запуск автотестов

```bash
# Все тесты
pytest tests/test_golden_set.py -v

# Конкретный тест
pytest tests/test_golden_set.py::TestGoldenSet::test_golden_case_gs_001 -v
```

### Ручное тестирование

**Примеры вопросов для тестирования:**

1. **Must-match кейс (P1):**
   - "Яйца приехали разбитые, что делать?"
   - Ожидается: `auto_answer`, тег "Неаккуратная доставка"

2. **Эскалация:**
   - "Можно ли оштрафовать курьера?"
   - Ожидается: `route_to_curator`

3. **Недостаточно данных:**
   - "Заказ задержался, но непонятно почему"
   - Ожидается: `route_to_curator`

---

## 🔍 ОТЛАДКА

### Проверка логов

```bash
# Последние логи explainability
tail -f logs/explainability/explainability_$(date +%Y-%m-%d).jsonl

# Поиск по user_id
grep '"user_id": 123' logs/explainability/*.jsonl

# Поиск по decision_route
grep '"decision_route": "route_to_curator"' logs/explainability/*.jsonl
```

### Проверка confidence score

```bash
# Низкий confidence (< 0.6)
grep -E '"confidence_score": [0-5]\.[0-9]' logs/explainability/*.jsonl

# Высокий confidence (>= 0.8)
grep -E '"confidence_score": [89]\.[0-9]' logs/explainability/*.jsonl
```

---

## ⚙️ КОНФИГУРАЦИЯ

### Core Policy JSON

Основной конфиг: `src/ai/core_policy.json`

**Секции:**
- `must_match_cases` — обязательные кейсы (P0/P1/P2)
- `golden_set` — эталонные кейсы для тестов
- `confidence_routing` — настройки маршрутизации
- `response_validator` — правила валидации
- `tags` — теги обращений
- `rules` — правила доставки

### Изменение порогов confidence

В `src/ai/core_policy.json`:

```json
"confidence_routing": {
  "thresholds": {
    "auto_answer": 0.8,        // >= 0.8 → автоматический ответ
    "clarification_required": 0.6,  // >= 0.6 → уточняющий вопрос
    "route_to_curator": 0.0    // < 0.6 → эскалация
  }
}
```

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Проблема: Бот всегда отправляет к куратору

**Причина:** Низкий confidence score или нет релевантных FAQ

**Решение:**
1. Проверить логи explainability
2. Проверить, есть ли FAQ в базе данных
3. Проверить must-match кейсы в Core Policy JSON

### Проблема: Ответы не проходят валидацию

**Причина:** Ответ не содержит обязательные блоки

**Решение:**
1. Проверить `validation_result` в логах
2. Обновить промпты для Groq API
3. Проверить структуру ответа

### Проблема: Логи не создаются

**Причина:** Нет прав на создание директории `logs/explainability/`

**Решение:**
```bash
mkdir -p logs/explainability
chmod 755 logs/explainability
```

---

## 📚 ДОПОЛНИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ

- `docs/AUDIT_REPORT.md` — аудит текущей реализации
- `docs/EXTRACTION_REPORT.md` — извлечение данных
- `docs/MODEL_REPORT.md` — новая модель
- `docs/REWRITE_REPORT.md` — переписывание
- `docs/FINAL_REPORT.md` — финальный отчет

---

## ✅ ЧЕКЛИСТ ПЕРЕД ЗАПУСКОМ

- [ ] DATABASE_URL настроен в `.env`
- [ ] GROQ_API_KEY настроен в `.env`
- [ ] База данных содержит FAQ
- [ ] Директория `logs/explainability/` создана
- [ ] Автотесты проходят: `pytest tests/test_golden_set.py -v`

---

**Готово к использованию!** 🎉
