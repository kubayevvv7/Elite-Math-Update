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
    m.add("📝 Uyga vazifa boshqaruvi", "👥 Foydalanuvchilarni boshqarish")
    m.add("🚫 Bloklangan foydalanuvchilar", "💳 Kartalarni boshqarish")
    m.add("✅ Active users")
    return m

def user_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("📝 Test topshirish", "📈 Mening natijalarim")
    m.add("🎬 Videolar", "💰 Balans")
    m.add("✏️ Ismni tahrirlash", "📝 Uyga vazifa")
    m.add("💳 To'lov", "🧑🏻‍💻About founder")
    return m

def back_button():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("⬅️ Orqaga")
    return m

def generate_tests_menu():
    tests = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 0 OR is_homework IS NULL ORDER BY created_at ASC", fetch=True) or []
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Add 3 tests per row
    row = []
    for test_id, test_name in tests:
        button_text = f"{test_name} ({test_id})"
        row.append(button_text)
        if len(row) == 3:
            m.row(*row)
            row = []
    # Add remaining buttons
    if row:
        m.row(*row)
    m.add("⬅️ Orqaga")
    return m

def build_admin_balances(page=0):
    users = query_db("SELECT chat_id, student_name, balance FROM users ORDER BY balance DESC, student_name ASC", fetch=True) or []
    text = "💰 <b>Foydalanuvchilar Balanslar</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    
    if not users:
        text += "📭 Hozircha foydalanuvchilar yo'q"
        return text, kb
    
    # Pagination: 20 users per page
    users_per_page = 20
    total_users = len(users)
    total_pages = (total_users + users_per_page - 1) // users_per_page  # Ceiling division
    
    # Ensure page is within valid range
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    # Get users for current page
    start_idx = page * users_per_page
    end_idx = min(start_idx + users_per_page, total_users)
    page_users = users[start_idx:end_idx]
    
    # Display users (already sorted by balance DESC)
    for chat_id, name, balance in page_users:
        text += f"👤 {name}: {balance} som\n"
    
    # Add user buttons in 2 columns (ustun) format
    # First column: users 0-9 (10 buttons)
    # Second column: users 10-19 (10 buttons)
    # Each row has 2 buttons: one from first column, one from second column
    
    first_column = page_users[:10]  # First 10 users
    second_column = page_users[10:20] if len(page_users) > 10 else []  # Next 10 users
    
    # Create rows with 2 buttons each
    max_rows = max(len(first_column), len(second_column))
    for i in range(max_rows):
        row_buttons = []
        
        # Add button from first column if available
        if i < len(first_column):
            chat_id, name, balance = first_column[i]
            button_text = f"🔄 {name[:15]}"
            row_buttons.append(types.InlineKeyboardButton(text=button_text, callback_data=f"admin_update_balance:{chat_id}"))
        
        # Add button from second column if available
        if i < len(second_column):
            chat_id, name, balance = second_column[i]
            button_text = f"🔄 {name[:15]}"
            row_buttons.append(types.InlineKeyboardButton(text=button_text, callback_data=f"admin_update_balance:{chat_id}"))
        
        if row_buttons:
            kb.row(*row_buttons)
    
    # Add pagination buttons if needed
    if total_pages > 1:
        pagination_row = []
        if page > 0:
            pagination_row.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin_balances_page:{page - 1}"))
        if page < total_pages - 1:
            pagination_row.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"admin_balances_page:{page + 1}"))
        
        if pagination_row:
            kb.row(*pagination_row)
        
        # Add page indicator
        text += f"\n📄 Sahifa {page + 1}/{total_pages} (Jami: {total_users} ta)"
    
    return text, kb

