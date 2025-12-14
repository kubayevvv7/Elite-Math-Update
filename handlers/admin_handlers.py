import os
import re
import time
import logging
from datetime import datetime
from telebot import types
from config import bot, ADMIN_IDS, user_state, VIDEOS_FOLDER, logger
from database import query_db, get_balance, update_user_balance
from utils import admin_main_menu, back_button, generate_tests_menu, generate_test_id, extract_answers, build_admin_balances

@bot.message_handler(commands=['start', 'admin'])
def start(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🧑‍💼 Salom, admin!", reply_markup=admin_main_menu())
        return
    from database import load_profile
    from utils import user_main_menu
    existing_name = load_profile(message.chat.id)
    if existing_name:
        bot.send_message(message.chat.id, f"Assalomu alaykum, {existing_name}!", reply_markup=user_main_menu())
        user_state.setdefault(message.chat.id, {})["username"] = message.from_user.username or None
    else:
        bot.send_message(message.chat.id, "Assalomu alaykum! Ism familiyangizni kiriting:")
        user_state[message.chat.id] = {"step": "get_name", "username": message.from_user.username or None}

@bot.message_handler(commands=['results'])
def results_command(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) >= 2 and parts[1].lower() in ("today", "bugun"):
        today = datetime.now().strftime("%Y-%m-%d")
        rows = query_db(
            "SELECT student_name, username, tg_id, test_id, correct_count, incorrect_count, date "
            "FROM results WHERE date LIKE ? ORDER BY student_name ASC, username ASC, tg_id ASC, test_id ASC, date ASC",
            (f"{today}%",),
            fetch=True
        )
        if not rows:
            bot.send_message(message.chat.id, f"📭 Bugun hozircha natijalar yo'q.", reply_markup=admin_main_menu())
            return

        grouped = {}
        for r in rows:
            student_name, username, tg_id, test_id, correct, incorrect, date = r
            key = (student_name, username, tg_id)
            student_entry = grouped.setdefault(key, {})
            student_entry.setdefault(test_id, []).append((correct, incorrect, date))

        text = f"📅 <b>Bugungi natijalar ({today})</b>\n\n"
        for (student_name, username, tg_id), tests in grouped.items():
            user_display = f"@{username}" if username else f"tg:{tg_id}"
            text += f"🧑‍🎓 <b>{student_name}</b> ({user_display})\n"
            for test_id, attempts in tests.items():
                for attempt_num, (correct, incorrect, date) in enumerate(attempts, 1):
                    text += f"  {attempt_num}-natija: ✅ {correct} | ❌ {incorrect} | 🕓 {date} | 🆔 {test_id}\n"
            text += "\n"

        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "➕ Test qo'shish")
def add_test_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "🧾 Test nomini kiriting:", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "get_test_name"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_test_name")
def get_test_name(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)

    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ Test nomi bo'sh bo'lmasligi kerak.")
        return
    user_state[message.chat.id]["test_name"] = name
    user_state[message.chat.id]["step"] = "get_correct_answers"
    bot.send_message(message.chat.id, "To'g'ri javoblarni kiriting (masalan: XXX 1a2b3c...):")

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_correct_answers")
def save_test(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)

    data = user_state.pop(message.chat.id, {})
    text = message.text.strip()
    if not text or not any(ch.isdigit() for ch in text):
        bot.send_message(message.chat.id, "❌ Javoblar to'g'ri formatda bo'lishi kerak.")
        return
    if "-" in text:
        test_id, answers = text.split("-", 1)
        test_id = test_id.strip()
    else:
        test_id = generate_test_id()
        answers = text
    correct = "".join(extract_answers(answers))
    query_db(
        "INSERT OR REPLACE INTO tests (test_id, test_name, correct_answers, created_at) VALUES (?, ?, ?, ?)",
        (test_id, data.get("test_name"), correct, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    bot.send_message(message.chat.id, f"✅ Test saqlandi!\n🆔 {test_id}\n📘 {data.get('test_name')}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "🗑 Testni o'chirish")
def delete_test_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    tests = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 0 OR is_homework IS NULL ORDER BY created_at DESC", fetch=True)
    if not tests:
        bot.send_message(message.chat.id, "📭 O'chirish uchun testlar yo'q.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for test_id, test_name in tests:
        kb.add(f"❌ {test_name} ({test_id})")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "O'chirish uchun testni tanlang:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "delete_test"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "delete_test")
def delete_selected_test(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)
    test_id = message.text.split("(")[-1].replace(")", "").strip()
    test = query_db("SELECT test_name FROM tests WHERE test_id = ?", (test_id,), fetch=True)
    if not test:
        bot.send_message(message.chat.id, "❌ Test topilmadi.")
        return
    query_db("DELETE FROM tests WHERE test_id = ?", (test_id,))
    query_db("DELETE FROM results WHERE test_id = ?", (test_id,))
    query_db("DELETE FROM videos WHERE test_id = ?", (test_id,))
    if VIDEOS_FOLDER and os.path.isdir(VIDEOS_FOLDER):
        try:
            for f in os.listdir(VIDEOS_FOLDER):
                if f.startswith(test_id):
                    try:
                        os.remove(os.path.join(VIDEOS_FOLDER, f))
                    except Exception:
                        pass
        except Exception:
            pass
    user_state.pop(message.chat.id, None)
    bot.send_message(message.chat.id, f"✅ Test o'chirildi!\n🆔 {test_id}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "🎬 Video qo'shish")
def add_video_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    tests = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 0 OR is_homework IS NULL ORDER BY created_at DESC", fetch=True)
    if not tests:
        bot.send_message(message.chat.id, "📭 Hozircha testlar mavjud emas. Avval test qo'shing.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for test_id, test_name in tests:
        kb.add(f"🎬 {test_name} ({test_id})")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "Video qo'shish uchun test tanlang:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "select_test_for_video"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "select_test_for_video")
def select_test_for_video(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)
    test_id = message.text.split("(")[-1].replace(")", "").strip()
    user_state[message.chat.id] = {"step": "get_video_url", "test_id": test_id}
    bot.send_message(message.chat.id, "🎥 YouTube video linkini kiriting:")

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_video_url")
def get_video_url(message):
    video_url = message.text.strip()
    chat_id = message.chat.id
    state = user_state.get(chat_id, {})
    test_id = state.get("test_id")
    if not test_id:
        bot.send_message(chat_id, "❌ Ichki xato: test ID topilmadi.", reply_markup=admin_main_menu())
        user_state.pop(chat_id, None)
        return
    if not video_url.startswith("http"):
        bot.send_message(chat_id, "❌ To'g'ri YouTube linki kiriting!")
        return
    query_db(
        "INSERT OR REPLACE INTO videos (test_id, video_url, created_at) VALUES (?, ?, ?)",
        (test_id, video_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    user_state.pop(chat_id, None)
    bot.send_message(chat_id, f"✅ YouTube link saqlandi.\n🆔 {test_id}\n🔗 {video_url}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "🗑 Videoni o'chirish")
def delete_video_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    videos = query_db("SELECT v.test_id, t.test_name FROM videos v LEFT JOIN tests t ON v.test_id = t.test_id ORDER BY v.created_at DESC", fetch=True)
    if not videos:
        bot.send_message(message.chat.id, "📭 Hozircha hech qanday video qo'shilmagan.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for test_id, test_name in videos:
        kb.add(f"🗑 {test_name or 'Nomalum'} ({test_id})")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "O'chirish uchun videoni tanlang:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "delete_video"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "delete_video")
def delete_selected_video(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)
    test_id = message.text.split("(")[-1].replace(")", "").strip()
    video = query_db("SELECT video_url FROM videos WHERE test_id = ?", (test_id,), fetch=True)
    if not video:
        bot.send_message(message.chat.id, "❌ Bunday video topilmadi.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    query_db("DELETE FROM videos WHERE test_id = ?", (test_id,))
    if VIDEOS_FOLDER and os.path.isdir(VIDEOS_FOLDER):
        try:
            for f in os.listdir(VIDEOS_FOLDER):
                if f.startswith(test_id):
                    try:
                        os.remove(os.path.join(VIDEOS_FOLDER, f))
                    except Exception:
                        pass
        except Exception:
            pass
    user_state.pop(message.chat.id, None)
    bot.send_message(message.chat.id, f"✅ Video o'chirildi.\n🆔 {test_id}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and "(" in m.text and ")" in m.text and m.text != "⬅️ Orqaga")
def admin_view_results(message):
    test_id = message.text.split("(")[-1].replace(")", "").strip()
    test = query_db("SELECT test_name FROM tests WHERE test_id = ?", (test_id,), fetch=True)
    if not test:
        return
    results = query_db("SELECT student_name, username, tg_id, correct_count, incorrect_count, date FROM results WHERE test_id = ? ORDER BY id ASC", (test_id,), fetch=True)
    if not results:
        bot.send_message(message.chat.id, f"📭 Bu testni hali hech kim ishlamagan.\n🆔 {test_id}")
        return
    
    text = f"📊 <b>{test[0][0]}</b>\n🆔 {test_id}\n\n"
    
    grouped_by_student = {}
    for r in results:
        student_name, username, tg_id, correct, incorrect, date = r
        key = (student_name, username, tg_id)
        if key not in grouped_by_student:
            grouped_by_student[key] = []
        grouped_by_student[key].append((correct, incorrect, date))
    
    for (student_name, username, tg_id), attempts in grouped_by_student.items():
        user_display = f"@{username}" if username else f"tg:{tg_id}"
        text += f"🧑‍🎓 <b>{student_name}</b> ({user_display})\n"
        for attempt_num, (correct, incorrect, date) in enumerate(attempts, 1):
            text += f"  {attempt_num}-natijasi: ✅ {correct} | ❌ {incorrect} | 🕓 {date}\n"
        text += "\n"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📊 Natijalarni ko'rish")
def show_test_list(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    tests = query_db("SELECT * FROM tests WHERE is_homework = 0 OR is_homework IS NULL", fetch=True)
    if not tests:
        bot.send_message(message.chat.id, "📭 Hozircha testlar mavjud emas.", reply_markup=admin_main_menu())
        return
    bot.send_message(message.chat.id, "📋 Testlar ro'yxati:", reply_markup=generate_tests_menu())

@bot.message_handler(func=lambda m: m.text == "📅 Bugungi natijalar")
def show_today_results(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    rows = query_db(
        "SELECT student_name, username, tg_id, test_id, correct_count, incorrect_count, date "
        "FROM results WHERE date LIKE ? ORDER BY student_name ASC, username ASC, tg_id ASC, test_id ASC, date ASC",
        (f"{today}%",),
        fetch=True
    )
    if not rows:
        bot.send_message(message.chat.id, f"📭 Bugun hozircha natijalar yo'q.", reply_markup=admin_main_menu())
        return

    grouped = {}
    for r in rows:
        student_name, username, tg_id, test_id, correct, incorrect, date = r
        key = (student_name, username, tg_id)
        student_entry = grouped.setdefault(key, {})
        student_entry.setdefault(test_id, []).append((correct, incorrect, date))

    text = f"📅 <b>Bugungi natijalar ({today})</b>\n\n"
    for (student_name, username, tg_id), tests in grouped.items():
        user_display = f"@{username}" if username else f"tg:{tg_id}"
        text += f"🧑‍🎓 <b>{student_name}</b> ({user_display})\n"
        for test_id, attempts in tests.items():
            text += f"  🆔 <b>{test_id}</b>\n"
            for idx, (correct, incorrect, date) in enumerate(attempts, 1):
                text += f"    {idx}-natijasi: ✅ {correct} | ❌ {incorrect} | 🕓 {date}\n"
            text += "\n"
        text += "\n"

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Balans" and m.from_user.id in ADMIN_IDS)
def admin_show_balances(message):
    text, kb = build_admin_balances()
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("admin_update_balance:"))
def admin_update_balance(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "Ruxsat yo'q")
        return
    try:
        target = call.data.split(":", 1)[1]
        target_id = str(int(target))
    except Exception:
        bot.answer_callback_query(call.id, "Noto'g'ri ma'lumot")
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db("UPDATE users SET balance = 0, updated_at = ? WHERE chat_id = ?", (now, target_id))
    bot.answer_callback_query(call.id, f"✅ Balansi 0 ga o'rnatildi")
    text, kb = build_admin_balances()
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass

def go_back(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
    else:
        from utils import user_main_menu
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    user_state.pop(message.chat.id, None)

