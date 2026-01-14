import random
import re
from telebot import types
from database import query_db

def generate_test_id():
    prefix = random.choice("TABCDEF")
    digits = ''.join(random.choices("0123456789", k=4))
    return prefix + digits

def generate_homework_id():
    """5 talik ID generatsiya qiladi"""
    return ''.join(random.choices("0123456789", k=5))

def extract_answers(text):
    return [ch.lower() for ch in text if ch.lower() in ['a', 'b', 'c', 'd', 'e']]

def admin_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("➕ Test qo'shish", "📊 Natijalarni ko'rish")
    m.add("🗑 Testni o'chirish", "🎬 Video qo'shish")
    m.add("🗑 Videoni o'chirish", "📅 Bugungi natijalar")
    m.add("🧩 Viktorina savollari", "💰 Balans")
    m.add("📝 Uyga vazifa boshqaruvi")
    return m

def user_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("📝 Test topshirish", "📈 Mening natijalarim")
    m.add("🎬 Videolar", "💰 Balans")
    m.add("✏️ Ismni tahrirlash", "📝 Uyga vazifa")
    m.add("🧑🏻‍💻About founder")
    return m

def back_button():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("⬅️ Orqaga")
    return m

def generate_tests_menu():
    tests = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 0 OR is_homework IS NULL ORDER BY created_at DESC", fetch=True) or []
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for test_id, test_name in tests:
        m.add(f"{test_name} ({test_id})")
    m.add("⬅️ Orqaga")
    return m

def build_admin_balances():
    users = query_db("SELECT chat_id, student_name, balance FROM users ORDER BY student_name ASC", fetch=True) or []
    text = "💰 <b>Foydalanuvchilar Balanslar</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    
    if not users:
        text += "📭 Hozircha foydalanuvchilar yo'q"
        return text, kb
    
    for chat_id, name, balance in users:
        text += f"👤 {name}: {balance} som\n"
        kb.add(types.InlineKeyboardButton(text=f"🔄 {name}", callback_data=f"admin_update_balance:{chat_id}"))
    
    return text, kb

