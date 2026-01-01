#!/usr/bin/env python3
"""
Обучение классификатора для AI-куратора.

Использует данные из таблицы ml_cases для обучения модели классификации.
"""
import asyncio
import os
import sys
from pathlib import Path
import pickle
import asyncpg
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️  scikit-learn не установлен. Установите: pip install scikit-learn")

load_dotenv()


async def train_classifier():
    """Обучение классификатора на данных из ml_cases."""
    
    if not SKLEARN_AVAILABLE:
        print("❌ scikit-learn не установлен")
        sys.exit(1)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не найден в .env")
        sys.exit(1)
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(database_url)
        print("✅ Подключение к PostgreSQL установлено")
        
        # Получаем данные
        print("📊 Загрузка данных из ml_cases...")
        rows = await conn.fetch(
            "SELECT input, label FROM ml_cases WHERE label IS NOT NULL"
        )
        
        if not rows:
            print("❌ Нет данных для обучения")
            await conn.close()
            sys.exit(1)
        
        X = [row['input'] for row in rows]
        y = [row['label'] for row in rows]
        
        print(f"  ✅ Загружено {len(X)} примеров")
        print(f"  ✅ Уникальных меток: {len(set(y))}")
        
        # Разделяем на train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"\n📊 Разделение данных:")
        print(f"  • Обучающая выборка: {len(X_train)} примеров")
        print(f"  • Тестовая выборка: {len(X_test)} примеров")
        
        # Векторизация
        print("\n🔄 Векторизация текста...")
        vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X_train_vec = vectorizer.fit_transform(X_train)
        X_test_vec = vectorizer.transform(X_test)
        
        # Обучение
        print("🔄 Обучение модели (RandomForest)...")
        classifier = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        classifier.fit(X_train_vec, y_train)
        
        # Оценка
        print("📊 Оценка модели...")
        y_pred = classifier.predict(X_test_vec)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"\n✅ Точность модели: {accuracy:.2%}")
        print("\n📊 Отчет по классификации:")
        print(classification_report(y_test, y_pred))
        
        # Сохранение модели
        model_dir = Path("models")
        model_dir.mkdir(exist_ok=True)
        
        classifier_path = model_dir / "classifier.pkl"
        vectorizer_path = model_dir / "vectorizer.pkl"
        
        with open(classifier_path, "wb") as f:
            pickle.dump(classifier, f)
        
        with open(vectorizer_path, "wb") as f:
            pickle.dump(vectorizer, f)
        
        print(f"\n💾 Модель сохранена:")
        print(f"  • {classifier_path}")
        print(f"  • {vectorizer_path}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при обучении: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(train_classifier())
