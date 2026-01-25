import sqlite3
from pathlib import Path

DB_PATH = Path("db/compiler.db")


# -------------------------------------------------
# Инициализация базы данных
# -------------------------------------------------

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS compiler_flags (
            name TEXT PRIMARY KEY
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flags TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            combination_id INTEGER,
            criterion TEXT,
            score REAL,
            PRIMARY KEY (combination_id, criterion),
            FOREIGN KEY (combination_id) REFERENCES combinations(id)
        )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------
# Флаги компилятора
# -------------------------------------------------

def insert_flag(flag: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO compiler_flags(name) VALUES (?)",
        (flag,)
    )

    conn.commit()
    conn.close()


def get_flags():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM compiler_flags")
    flags = [row[0] for row in cur.fetchall()]

    conn.close()
    return flags


def clear_flags():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM compiler_flags")

    conn.commit()
    conn.close()


# -------------------------------------------------
# Комбинации
# -------------------------------------------------

def insert_combination(flags_str: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO combinations(flags) VALUES (?)",
        (flags_str,)
    )

    cur.execute(
        "SELECT id FROM combinations WHERE flags = ?",
        (flags_str,)
    )

    combination_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    return combination_id


def get_combinations():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, flags FROM combinations")
    rows = cur.fetchall()

    conn.close()
    return rows


# -------------------------------------------------
# Результаты экспериментов
# -------------------------------------------------

def insert_score(flags_str: str, criterion: str, score: float):
    combination_id = insert_combination(flags_str)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO scores
        (combination_id, criterion, score)
        VALUES (?, ?, ?)
    """, (combination_id, criterion, score))

    conn.commit()
    conn.close()


def get_scores():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT c.flags, s.criterion, s.score
        FROM scores s
        JOIN combinations c ON c.id = s.combination_id
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def get_scores_by_criterion(criterion: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT c.flags, s.score
        FROM scores s
        JOIN combinations c ON c.id = s.combination_id
        WHERE s.criterion = ?
    """, (criterion,))

    rows = cur.fetchall()
    conn.close()

    return rows

# -------------------------------------------------
# Вспомогательные функции для очистки
# -------------------------------------------------

def delete_flag(flag_name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM compiler_flags WHERE name = ?", (flag_name,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def delete_all_flags():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM compiler_flags")
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted

def delete_all_scores():
    """Удаляет все результаты из таблицы scores"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM scores")
    conn.commit()
    deleted_count = cur.rowcount
    conn.close()
    return deleted_count

def delete_all_combinations():
    """Удаляет все комбинации из таблицы combinations"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM combinations")
    deleted_count = cur.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def clear_all_data():
    """Очищает все данные из всех таблиц"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Удаляем данные из всех таблиц
    cur.execute("DELETE FROM scores")
    cur.execute("DELETE FROM combinations")
    cur.execute("DELETE FROM compiler_flags")
    
    # Сбрасываем все счетчики autoincrement
    cur.execute("DELETE FROM sqlite_sequence")
    
    conn.commit()
    conn.close()
    
    return True
