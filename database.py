import sqlite3
import logging
from datetime import datetime
from config import DB_FILE, user_profiles

logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id TEXT PRIMARY KEY,
            student_name TEXT,
            username TEXT,
            updated_at TEXT,
            name_changes INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS tests (
            test_id TEXT PRIMARY KEY,
            test_name TEXT,
            correct_answers TEXT,
            created_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            username TEXT,
            tg_id TEXT,
            test_id TEXT,
            correct_count INTEGER,
            incorrect_count INTEGER,
            date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT UNIQUE,
            video_url TEXT,
            created_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            file_id TEXT,
            correct_answer TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            sent_at TEXT,
            hours_remaining INTEGER DEFAULT 24,
            sent_to_users INTEGER DEFAULT 0
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            username TEXT,
            student_name TEXT,
            blocked_at TEXT,
            blocked_by TEXT,
            reason TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT NOT NULL,
            card_owner TEXT,
            bank_name TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            student_name TEXT,
            amount INTEGER DEFAULT 15000,
            status TEXT DEFAULT 'pending',
            card_number TEXT,
            payment_date TEXT,
            verified_date TEXT,
            verified_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            username TEXT,
            student_name TEXT,
            subscription_type TEXT DEFAULT 'monthly',
            price INTEGER DEFAULT 15000,
            start_date TEXT,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            payment_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()

    # Add name_changes column if not exists
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]  
    if "name_changes" not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN name_changes INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass

    if "balance" not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass

    # Add is_homework column for tests
    cur.execute("PRAGMA table_info(tests)")
    test_cols = [r[1] for r in cur.fetchall()]
    if "is_homework" not in test_cols:
        try:
            cur.execute("ALTER TABLE tests ADD COLUMN is_homework INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass

    # Add columns for quizzes
    cur.execute("PRAGMA table_info(quizzes)")
    quiz_cols = [r[1] for r in cur.fetchall()]
    if "correct_answer" not in quiz_cols:
        try:
            cur.execute("ALTER TABLE quizzes ADD COLUMN correct_answer TEXT")
            conn.commit()
        except Exception:
            pass
    if "sent_at" not in quiz_cols:
        try:
            cur.execute("ALTER TABLE quizzes ADD COLUMN sent_at TEXT")
            conn.commit()
        except Exception:
            pass
    if "hours_remaining" not in quiz_cols:
        try:
            cur.execute("ALTER TABLE quizzes ADD COLUMN hours_remaining INTEGER DEFAULT 24")
            conn.commit()
        except Exception:
            pass
    if "sent_to_users" not in quiz_cols:
        try:
            cur.execute("ALTER TABLE quizzes ADD COLUMN sent_to_users INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass

    conn.close()

def query_db(query, params=(), fetch=False, many=False):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
        cur = conn.cursor()
        if many:
            cur.executemany(query, params)
        else:
            cur.execute(query, params)
        rows = cur.fetchall() if fetch else None
        conn.commit()
        conn.close()
        return rows
    except sqlite3.Error as e:
        logger.exception("DB error")
        try:
            conn.close()
        except Exception:
            pass
        return None

def save_profile(chat_id, student_name, username=None, name_changes=None):
    """Insert or update user profile. If name_changes is None, preserve existing value (or default 0)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = query_db("SELECT name_changes FROM users WHERE chat_id = ?", (str(chat_id),), fetch=True)
    existing_count = existing[0][0] if existing else 0
    if name_changes is None:
        name_changes = existing_count or 0
    query_db(
        "INSERT OR REPLACE INTO users (chat_id, student_name, username, updated_at, name_changes) VALUES (?, ?, ?, ?, ?)",
        (str(chat_id), student_name, username, now, name_changes)
    )
    user_profiles[chat_id] = student_name

def load_profile(chat_id):
    if chat_id in user_profiles:
        return user_profiles[chat_id]
    r = query_db("SELECT student_name FROM users WHERE chat_id = ?", (str(chat_id),), fetch=True)
    if r:
        user_profiles[chat_id] = r[0][0]
        return r[0][0]
    return None

def get_name_changes(chat_id):
    r = query_db("SELECT name_changes FROM users WHERE chat_id = ?", (str(chat_id),), fetch=True)
    if r and r[0][0] is not None:
        return int(r[0][0])
    return 0

def increment_name_changes(chat_id):
    current = get_name_changes(chat_id)
    new = current + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exists = query_db("SELECT 1 FROM users WHERE chat_id = ?", (str(chat_id),), fetch=True)
    if exists:
        query_db("UPDATE users SET name_changes = ?, updated_at = ? WHERE chat_id = ?", (new, now, str(chat_id)))
    else:
        query_db("INSERT INTO users (chat_id, student_name, username, updated_at, name_changes) VALUES (?, ?, ?, ?, ?)",
                 (str(chat_id), "", None, now, new))
    return new

def get_balance(chat_id):
    r = query_db("SELECT balance FROM users WHERE chat_id = ?", (str(chat_id),), fetch=True)
    if r and r[0][0] is not None:
        return int(r[0][0])
    return 0

def update_user_balance(chat_id, amount):
    """User balansini yangilaydi"""
    current = get_balance(chat_id)
    new_balance = current + amount
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db("UPDATE users SET balance = ?, updated_at = ? WHERE chat_id = ?", (new_balance, now, str(chat_id)))
    return new_balance

def get_all_active_quizzes():
    return query_db("SELECT id, file_path, file_id, correct_answer, created_at, sent_at, hours_remaining, sent_to_users FROM quizzes WHERE active = 1 ORDER BY created_at DESC", fetch=True)

def get_unsent_quiz():
    """Yuborilmagan viktorina savolini qaytaradi"""
    quizzes = query_db("SELECT id, file_id, correct_answer, sent_to_users FROM quizzes WHERE active = 1 AND sent_to_users = 0 AND file_id IS NOT NULL AND file_id != '' ORDER BY created_at ASC LIMIT 1", fetch=True)
    return quizzes[0] if quizzes else None

def mark_quiz_as_sent(quiz_id):
    """Viktorina savolini yuborilgan deb belgilaydi"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db("UPDATE quizzes SET sent_to_users = 1, sent_at = ? WHERE id = ?", (now, quiz_id))

def get_quiz_hours_remaining(quiz_id):
    """Viktorina savolini necha soat qolganini qaytaradi"""
    result = query_db("SELECT sent_at, hours_remaining FROM quizzes WHERE id = ?", (quiz_id,), fetch=True)
    if not result:
        return None
    sent_at_str, hours_remaining = result[0]
    if not sent_at_str:
        return None
    try:
        sent_at = datetime.strptime(sent_at_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        elapsed = (now - sent_at).total_seconds() / 3600
        remaining = max(0, hours_remaining - elapsed)
        return remaining
    except Exception:
        return None

def create_quiz(file_path, file_id, correct_answer):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db(
        "INSERT INTO quizzes (file_path, file_id, correct_answer, active, created_at, sent_at, hours_remaining, sent_to_users) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (file_path, file_id, correct_answer, 1, now, None, 24, 0)
    )

