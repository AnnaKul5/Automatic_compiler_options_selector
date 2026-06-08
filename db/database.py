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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combination_flag (
            combination_id INTEGER NOT NULL,
            flag_id INTEGER NOT NULL,

            PRIMARY KEY (combination_id, flag_id),

            FOREIGN KEY (combination_id)
                REFERENCES combinations(id)
                ON DELETE CASCADE,

            FOREIGN KEY (flag_id)
                REFERENCES compiler_flags(id)
                ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            combination_id INTEGER NOT NULL,
            criterion TEXT NOT NULL,
            score REAL NOT NULL,

            PRIMARY KEY (combination_id, criterion),

            FOREIGN KEY (combination_id)
                REFERENCES combinations(id)
                ON DELETE CASCADE
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
    cur.execute("INSERT INTO combinations DEFAULT VALUES")
    combination_id = cur.lastrowid
    flags = flags_str.split()

    for flag in flags:
        cur.execute(
            "SELECT id FROM compiler_flags WHERE name = ?",
            (flag,)
        )
        row = cur.fetchone()
        if row is None:
            continue

        flag_id = row[0]
        cur.execute("""
            INSERT INTO combination_flag
            (combination_id, flag_id)
            VALUES (?, ?)
        """, (combination_id, flag_id))

    conn.commit()
    conn.close()
    return combination_id


def get_combination_flags(combination_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT f.name
        FROM combination_flag cf
        JOIN compiler_flags f
            ON cf.flag_id = f.id
        WHERE cf.combination_id = ?
        ORDER BY f.name
    """, (combination_id,))

    flags = [row[0] for row in cur.fetchall()]
    conn.close()
    return " ".join(flags)


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
        SELECT combination_id, criterion, score
        FROM scores
    """)

    rows = cur.fetchall()
    conn.close()
    result = []

    for combination_id, criterion, score in rows:
        flags = get_combination_flags(combination_id)
        result.append((flags, criterion, score))

    return result


def get_scores_by_criterion(criterion: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT combination_id, score
        FROM scores
        WHERE criterion = ?
    """, (criterion,))

    rows = cur.fetchall()
    conn.close()
    result = []
    for combination_id, score in rows:
        flags_str = get_combination_flags(combination_id)
        result.append((flags_str, score))
    return result

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
    """Удаляет все комбинации из таблицы combination_flag"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM combination_flag")
    deleted_count = cur.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def clear_all_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM scores")
    cur.execute("DELETE FROM combination_flag")
    cur.execute("DELETE FROM combinations")
    cur.execute("DELETE FROM compiler_flags")

    cur.execute("DELETE FROM sqlite_sequence")

    conn.commit()
    conn.close()

    return True
