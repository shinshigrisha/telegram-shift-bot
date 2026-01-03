#!/usr/bin/env python3
"""
Скрипт для разбиения PDF файла на chunks для базы знаний.

Использование:
    python scripts/pdf_to_chunks.py

PDF файл должен находиться по пути: docs/Data.pdf

Результат:
    Выводит информацию о созданных chunks в консоль.
    Chunks можно использовать для дальнейшей обработки (например, сохранения в БД).

Требования:
    pip install pypdf
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    from pypdf import PdfReader
except ImportError:
    print("❌ Ошибка: библиотека pypdf не установлена")
    print("\nУстановите её командой:")
    print("    pip install pypdf")
    sys.exit(1)


@dataclass
class PDFChunk:
    """Структура данных для одного chunk из PDF."""
    source: str
    chunk_index: int
    content: str

    def to_dict(self) -> dict:
        """Преобразовать chunk в словарь."""
        return {
            "source": self.source,
            "chunk_index": self.chunk_index,
            "content": self.content,
        }


def read_pdf(file_path: Path) -> str:
    """
    Прочитать PDF файл и извлечь весь текст.
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Извлечённый текст из PDF
        
    Raises:
        FileNotFoundError: Если файл не найден
        Exception: При ошибке чтения PDF
    """
    if not file_path.exists():
        raise FileNotFoundError(f"PDF файл не найден: {file_path}")
    
    print(f"📄 Чтение PDF файла: {file_path}")
    
    try:
        reader = PdfReader(str(file_path))
        text_parts = []
        
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text:
                text_parts.append(text)
                print(f"  ✅ Страница {page_num}: извлечено {len(text)} символов")
        
        full_text = "\n".join(text_parts)
        print(f"✅ Всего извлечено {len(full_text)} символов из {len(reader.pages)} страниц")
        
        return full_text
    
    except Exception as e:
        raise Exception(f"Ошибка при чтении PDF: {e}") from e


def clean_text(text: str) -> str:
    """
    Очистить текст от мусора.
    
    Удаляет:
    - Лишние пробелы (более одного подряд)
    - Лишние переносы строк (более двух подряд)
    - Пробелы в начале и конце строк
    
    Args:
        text: Исходный текст
        
    Returns:
        Очищенный текст
    """
    # Заменяем множественные пробелы на один
    text = re.sub(r' +', ' ', text)
    
    # Заменяем множественные переносы строк (более 2) на два
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Убираем пробелы в начале и конце каждой строки
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Убираем пробелы в начале и конце всего текста
    text = text.strip()
    
    return text


def split_into_chunks(
    text: str,
    min_chunk_size: int = 500,
    max_chunk_size: int = 800,
) -> List[str]:
    """
    Разбить текст на логические chunks.
    
    Алгоритм:
    1. Пытаемся разбить по предложениям (точка + пробел/перенос)
    2. Если предложение слишком длинное, разбиваем по переносам строк
    3. Если chunk получается меньше min_chunk_size, объединяем со следующим
    4. Если chunk получается больше max_chunk_size, разбиваем принудительно
    
    Args:
        text: Текст для разбиения
        min_chunk_size: Минимальный размер chunk (символов)
        max_chunk_size: Максимальный размер chunk (символов)
        
    Returns:
        Список текстовых chunks
    """
    if not text:
        return []
    
    # Сначала разбиваем по предложениям (точка + пробел/перенос строки)
    # Паттерн: точка, за которой следует пробел или перенос строки
    sentences = re.split(r'\.(\s+|\n+)', text)
    
    # Объединяем разделители обратно с предложениями
    chunks = []
    current_chunk = ""
    
    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        
        # Если следующая часть - разделитель, добавляем его к предложению
        if i + 1 < len(sentences) and re.match(r'^\s+$', sentences[i + 1]):
            sentence += sentences[i + 1]
            i += 2
        else:
            i += 1
        
        # Если предложение само по себе больше max_chunk_size, разбиваем по переносам
        if len(sentence) > max_chunk_size:
            # Разбиваем по переносам строк
            lines = sentence.split('\n')
            for line in lines:
                if len(line) > max_chunk_size:
                    # Если строка всё ещё слишком длинная, разбиваем принудительно
                    while len(line) > max_chunk_size:
                        chunks.append(line[:max_chunk_size])
                        line = line[max_chunk_size:]
                    if line:
                        current_chunk += line + '\n'
                else:
                    if len(current_chunk) + len(line) + 1 > max_chunk_size:
                        chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                    else:
                        current_chunk += line + '\n'
        else:
            # Проверяем, нужно ли добавить к текущему chunk или создать новый
            if len(current_chunk) + len(sentence) > max_chunk_size:
                # Текущий chunk достаточно большой, сохраняем его
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Добавляем к текущему chunk
                current_chunk += sentence
    
    # Добавляем последний chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Объединяем слишком маленькие chunks
    merged_chunks = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        
        # Если chunk слишком маленький, пытаемся объединить со следующим
        if len(current) < min_chunk_size and i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            combined = current + '\n\n' + next_chunk
            
            # Если объединённый chunk не превышает max_chunk_size, объединяем
            if len(combined) <= max_chunk_size:
                merged_chunks.append(combined)
                i += 2
                continue
        
        merged_chunks.append(current)
        i += 1
    
    return merged_chunks


def create_chunks_from_pdf(
    pdf_path: Path,
    source_name: str = "Data.pdf",
    min_chunk_size: int = 500,
    max_chunk_size: int = 800,
) -> List[PDFChunk]:
    """
    Создать chunks из PDF файла.
    
    Args:
        pdf_path: Путь к PDF файлу
        source_name: Имя источника (для поля source)
        min_chunk_size: Минимальный размер chunk
        max_chunk_size: Максимальный размер chunk
        
    Returns:
        Список PDFChunk объектов
    """
    # Читаем PDF
    raw_text = read_pdf(pdf_path)
    
    # Очищаем текст
    print("\n🧹 Очистка текста...")
    cleaned_text = clean_text(raw_text)
    print(f"✅ После очистки: {len(cleaned_text)} символов")
    
    # Разбиваем на chunks
    print(f"\n✂️  Разбиение на chunks (размер: {min_chunk_size}-{max_chunk_size} символов)...")
    text_chunks = split_into_chunks(cleaned_text, min_chunk_size, max_chunk_size)
    print(f"✅ Создано {len(text_chunks)} chunks")
    
    # Создаём структуры данных
    chunks = []
    for index, content in enumerate(text_chunks):
        chunk = PDFChunk(
            source=source_name,
            chunk_index=index,
            content=content,
        )
        chunks.append(chunk)
    
    return chunks


def print_chunks_info(chunks: List[PDFChunk]) -> None:
    """
    Вывести информацию о созданных chunks.
    
    Args:
        chunks: Список chunks
    """
    if not chunks:
        print("\n⚠️  Chunks не созданы")
        return
    
    print("\n" + "=" * 70)
    print("📊 ИНФОРМАЦИЯ О CHUNKS")
    print("=" * 70)
    print(f"Всего chunks: {len(chunks)}")
    
    # Статистика по размерам
    sizes = [len(chunk.content) for chunk in chunks]
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    min_size = min(sizes) if sizes else 0
    max_size = max(sizes) if sizes else 0
    
    print(f"\n📏 Размеры chunks:")
    print(f"  • Минимальный: {min_size} символов")
    print(f"  • Максимальный: {max_size} символов")
    print(f"  • Средний: {avg_size:.1f} символов")
    
    # Показываем первые 3 chunks как примеры
    print(f"\n📄 Примеры chunks (первые 3):")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n  Chunk #{chunk.chunk_index}:")
        print(f"    Source: {chunk.source}")
        print(f"    Размер: {len(chunk.content)} символов")
        print(f"    Превью: {chunk.content[:100]}...")


def main() -> None:
    """Главная функция скрипта."""
    # Определяем путь к PDF
    script_dir = Path(__file__).parent.parent
    pdf_path = script_dir / "docs" / "Data.pdf"
    
    print("=" * 70)
    print("📚 РАЗБИЕНИЕ PDF НА CHUNKS")
    print("=" * 70)
    print(f"PDF файл: {pdf_path}")
    
    try:
        # Создаём chunks
        chunks = create_chunks_from_pdf(
            pdf_path=pdf_path,
            source_name="Data.pdf",
            min_chunk_size=500,
            max_chunk_size=800,
        )
        
        # Выводим информацию
        print_chunks_info(chunks)
        
        print("\n" + "=" * 70)
        print("✅ ГОТОВО")
        print("=" * 70)
        print("\n💡 Chunks готовы к использованию.")
        print("   Для сохранения в БД или дальнейшей обработки используйте:")
        print("   chunks = create_chunks_from_pdf(pdf_path)")
        print("   for chunk in chunks:")
        print("       data = chunk.to_dict()  # Преобразовать в словарь")
        
    except FileNotFoundError as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
