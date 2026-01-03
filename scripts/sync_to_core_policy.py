#!/usr/bin/env python3
"""
Скрипт для синхронизации данных из delivery_curator_config.json в core_policy.json.

Обновляет Core Policy JSON данными из старого конфига.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Загрузить JSON файл."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """Сохранить JSON файл."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_must_match_cases(old_config: Dict[str, Any], core_policy: Dict[str, Any]) -> None:
    """Синхронизировать must-match кейсы."""
    old_cases = old_config.get("must_match_cases", {}).get("cases", [])
    
    # Добавляем приоритеты к старым кейсам, если их нет
    for case in old_cases:
        if "priority" not in case:
            # Определяем приоритет по ID
            case_id = case.get("id", "")
            if "P0" in case_id or "RET_P0" in case_id or "HL_002" in case_id or "HL_003" in case_id:
                case["priority"] = "P0"
            elif "PAY" in case_id or "HL" in case_id:
                case["priority"] = "P1"
            else:
                case["priority"] = "P1"  # По умолчанию P1
    
    # Объединяем со существующими кейсами в Core Policy
    existing_cases = {c.get("id"): c for c in core_policy.get("must_match_cases", {}).get("cases", [])}
    
    # Добавляем новые кейсы
    for case in old_cases:
        case_id = case.get("id")
        if case_id not in existing_cases:
            existing_cases[case_id] = case
    
    # Обновляем Core Policy
    if "must_match_cases" not in core_policy:
        core_policy["must_match_cases"] = {"cases": []}
    
    core_policy["must_match_cases"]["cases"] = list(existing_cases.values())


def sync_golden_set(old_config: Dict[str, Any], core_policy: Dict[str, Any]) -> None:
    """Синхронизировать Golden Set."""
    old_golden = old_config.get("golden_set", [])
    
    # Объединяем со существующими кейсами
    existing_cases = {c.get("id"): c for c in core_policy.get("golden_set", {}).get("cases", [])}
    
    # Добавляем новые кейсы
    for case in old_golden:
        case_id = case.get("id")
        if case_id not in existing_cases:
            existing_cases[case_id] = case
    
    # Обновляем Core Policy
    if "golden_set" not in core_policy:
        core_policy["golden_set"] = {"cases": []}
    
    core_policy["golden_set"]["cases"] = list(existing_cases.values())
    core_policy["golden_set"]["total"] = len(core_policy["golden_set"]["cases"])


def sync_rules(old_config: Dict[str, Any], core_policy: Dict[str, Any]) -> None:
    """Синхронизировать правила."""
    old_rules = old_config.get("knowledge_base", {}).get("rules", [])
    
    # Объединяем со существующими правилами
    existing_rules = {r.get("id"): r for r in core_policy.get("rules", {}).get("items", [])}
    
    # Добавляем новые правила
    for rule in old_rules:
        rule_id = rule.get("id")
        if rule_id not in existing_rules:
            existing_rules[rule_id] = rule
    
    # Обновляем Core Policy
    if "rules" not in core_policy:
        core_policy["rules"] = {"items": []}
    
    core_policy["rules"]["items"] = list(existing_rules.values())


def sync_tags(old_config: Dict[str, Any], core_policy: Dict[str, Any]) -> None:
    """Синхронизировать теги."""
    old_tags = old_config.get("knowledge_base", {}).get("tags", [])
    
    # Объединяем со существующими тегами
    existing_tags = {t.get("tag"): t for t in core_policy.get("tags", [])}
    
    # Добавляем новые теги
    for tag in old_tags:
        tag_name = tag.get("tag")
        if tag_name not in existing_tags:
            # Преобразуем формат
            new_tag = {
                "id": f"TAG_{len(existing_tags) + 1:03d}",
                "tag": tag_name,
                "description": tag.get("description", ""),
                "responsible": tag.get("responsible", "Курьер"),
                "priority": "high" if tag.get("priority") == "Высокий" else "medium",
                "category": "Доставка"  # По умолчанию
            }
            existing_tags[tag_name] = new_tag
    
    # Обновляем Core Policy
    core_policy["tags"] = list(existing_tags.values())


def main():
    """Главная функция синхронизации."""
    print("=" * 70)
    print("🔄 СИНХРОНИЗАЦИЯ ДАННЫХ В CORE POLICY JSON")
    print("=" * 70)
    
    project_root = Path(__file__).parent.parent
    old_config_path = project_root / "src" / "ai" / "delivery_curator_config.json"
    core_policy_path = project_root / "src" / "ai" / "core_policy.json"
    
    # Загружаем файлы
    print("\n📄 Загрузка файлов...")
    old_config = load_json_file(old_config_path)
    core_policy = load_json_file(core_policy_path)
    print(f"  ✅ Старый конфиг загружен: {len(old_config)} секций")
    print(f"  ✅ Core Policy загружен: версия {core_policy.get('meta', {}).get('version', 'unknown')}")
    
    # Синхронизируем данные
    print("\n🔄 Синхронизация данных...")
    
    print("  📊 Must-match кейсы...")
    sync_must_match_cases(old_config, core_policy)
    print(f"     ✅ Обновлено: {len(core_policy['must_match_cases']['cases'])} кейсов")
    
    print("  📊 Golden Set...")
    sync_golden_set(old_config, core_policy)
    print(f"     ✅ Обновлено: {len(core_policy['golden_set']['cases'])} кейсов")
    
    print("  📊 Правила...")
    sync_rules(old_config, core_policy)
    print(f"     ✅ Обновлено: {len(core_policy['rules']['items'])} правил")
    
    print("  📊 Теги...")
    sync_tags(old_config, core_policy)
    print(f"     ✅ Обновлено: {len(core_policy['tags'])} тегов")
    
    # Сохраняем обновленный Core Policy
    print("\n💾 Сохранение обновленного Core Policy JSON...")
    save_json_file(core_policy_path, core_policy)
    print(f"  ✅ Сохранено: {core_policy_path}")
    
    # Статистика
    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 70)
    print(f"  Must-match кейсов: {len(core_policy['must_match_cases']['cases'])}")
    print(f"  Golden Set кейсов: {len(core_policy['golden_set']['cases'])}")
    print(f"  Правил: {len(core_policy['rules']['items'])}")
    print(f"  Тегов: {len(core_policy['tags'])}")
    
    # Приоритеты must-match
    p0 = sum(1 for c in core_policy['must_match_cases']['cases'] if c.get('priority') == 'P0')
    p1 = sum(1 for c in core_policy['must_match_cases']['cases'] if c.get('priority') == 'P1')
    p2 = sum(1 for c in core_policy['must_match_cases']['cases'] if c.get('priority') == 'P2')
    print(f"\n  Приоритеты must-match:")
    print(f"    P0: {p0}, P1: {p1}, P2: {p2}")
    
    print("\n✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА")


if __name__ == "__main__":
    main()
