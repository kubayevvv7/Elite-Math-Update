import os
import re
import time
import logging
from datetime import datetime
from telebot import types
from config import bot, ADMIN_IDS, user_state, VIDEOS_FOLDER, logger
from database import query_db, get_balance, update_user_balance
from utils import admin_main_menu, back_button, generate_tests_menu, generate_test_id, extract_answers, build_admin_balances
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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
    tests = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 0 OR is_homework IS NULL ORDER BY created_at ASC", fetch=True)
    if not tests:
        bot.send_message(message.chat.id, "📭 O'chirish uchun testlar yo'q.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for test_id, test_name in tests:
        button_text = f"❌ {test_name} ({test_id})"
        row.append(button_text)
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
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
    tests = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 0 OR is_homework IS NULL ORDER BY created_at ASC", fetch=True)
    if not tests:
        bot.send_message(message.chat.id, "📭 Hozircha testlar mavjud emas. Avval test qo'shing.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for test_id, test_name in tests:
        button_text = f"🎬 {test_name} ({test_id})"
        row.append(button_text)
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
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
    videos = query_db("SELECT v.test_id, t.test_name FROM videos v LEFT JOIN tests t ON v.test_id = t.test_id ORDER BY v.created_at ASC", fetch=True)
    if not videos:
        bot.send_message(message.chat.id, "📭 Hozircha hech qanday video qo'shilmagan.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for test_id, test_name in videos:
        button_text = f"🗑 {test_name or 'Nomalum'} ({test_id})"
        row.append(button_text)
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
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

@bot.message_handler(func=lambda m: m.text == "📊 Natijalarni ko'rish")
def show_test_list(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    tests = query_db("SELECT * FROM tests WHERE is_homework = 0 OR is_homework IS NULL", fetch=True)
    if not tests:
        bot.send_message(message.chat.id, "📭 Hozircha testlar mavjud emas.", reply_markup=admin_main_menu())
        return
    bot.send_message(message.chat.id, "📋 Testlar ro'yxati (bir qatorda 3ta test):", reply_markup=generate_tests_menu())

def get_score_color(correct_count):
    """Return color based on correct count: <15 red, 16-24 yellow, 25-30 green"""
    correct = int(correct_count)
    if correct <= 15:
        return colors.HexColor("#F40000")  # Light Red
    elif 16 <= correct <= 24:
        return colors.HexColor("#F7F700")  # Light Yellow
    else:  # 25-30
        return colors.HexColor("#01F901")  # Light Green

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

    # Build table and generate PDF for today's results (only first attempt per student per test)
    data = [["Ism Familiya", "Test", "To'g'ri", "Noto'g'ri", "Vaqti", "Urinishlar"]]
    seen = set()
    temp_data = []
    for r in rows:
        student_name, username, tg_id, test_id, correct, incorrect, date = r
        key = (student_name, test_id)
        if key not in seen:
            temp_data.append([student_name, str(test_id), str(correct), str(incorrect), str(date), "1"])
            seen.add(key)
    
    # Sort by correct count (index 2) in descending order - most solved at top
    temp_data.sort(key=lambda x: int(x[2]), reverse=True)
    data.extend(temp_data)

    # create PDF with table and colored rows
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10*mm, rightMargin=10*mm, topMargin=15*mm, bottomMargin=15*mm)
    elements = []
    styles = getSampleStyleSheet()
    title_text = Paragraph(f"Bugungi natijalar — {today}", styles['Heading2'])
    elements.append(title_text)
    elements.append(Spacer(1, 6*mm))
    # Space for image
    elements.append(Spacer(1, 30*mm))

    col_widths = [40*mm, 30*mm, 18*mm, 18*mm, 35*mm, 18*mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Build styles with conditional coloring for each row
    styles_list = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2196F3')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('ALIGN',(0,1),(1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),4),
        ('RIGHTPADDING',(0,0),(-1,-1),4),
    ]
    
    # Add row colors based on correct count
    for row_idx in range(1, len(data)):
        correct_count = int(data[row_idx][2])
        if correct_count <= 15:
            bg_color = colors.HexColor('#FF5555')  # Bright red
        elif 16 <= correct_count <= 24:
            bg_color = colors.HexColor('#FFFF88')  # Bright yellow
        else:  # 25-30
            bg_color = colors.HexColor('#55FF55')  # Bright green
        
        styles_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
        styles_list.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.black))
        styles_list.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica'))
        styles_list.append(('FONTSIZE', (0, row_idx), (-1, row_idx), 9))
    
    table.setStyle(TableStyle(styles_list))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    bot.send_document(message.chat.id, (f"today_results_{today}.pdf", buf), reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Balans" and m.from_user.id in ADMIN_IDS)
def admin_show_balances(message):
    text, kb = build_admin_balances()
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("admin_balances_page:"))
def admin_balances_pagination(call):
    """Sahifalash uchun callback handler"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "Ruxsat yo'q")
        return
    
    try:
        page = int(call.data.split(":", 1)[1])
    except Exception:
        bot.answer_callback_query(call.id, "Noto'g'ri ma'lumot")
        return
    
    bot.answer_callback_query(call.id)
    text, kb = build_admin_balances(page)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass

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
    
    # Extract current page from message text if available
    current_page = 0
    try:
        message_text = call.message.text or ""
        if "Sahifa" in message_text:
            # Extract page number from text like "Sahifa 2/5"
            match = re.search(r'Sahifa (\d+)/(\d+)', message_text)
            if match:
                current_page = int(match.group(1)) - 1  # Convert to 0-based
    except Exception:
        pass
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db("UPDATE users SET balance = 0, updated_at = ? WHERE chat_id = ?", (now, target_id))
    bot.answer_callback_query(call.id, f"✅ Balansi 0 ga o'rnatildi")
    text, kb = build_admin_balances(current_page)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("view_test_result:"))
def view_test_result_callback(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "Ruxsat yo'q", show_alert=True)
        return
    test_id = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    
    test = query_db("SELECT test_name FROM tests WHERE test_id = ?", (test_id,), fetch=True)
    if not test:
        bot.send_message(call.message.chat.id, f"❌ Test topilmadi: {test_id}")
        return
    
    results = query_db("SELECT student_name, username, tg_id, correct_count, incorrect_count, date FROM results WHERE test_id = ? ORDER BY id ASC", (test_id,), fetch=True)
    if not results:
        bot.send_message(call.message.chat.id, f"📭 Bu testni hali hech kim ishlamagan.\n🆔 {test_id}")
        return
    
    # Build table and generate PDF to send to admin
    grouped_by_student = {}
    for r in results:
        student_name, username, tg_id, correct, incorrect, date = r
        key = (student_name, username, tg_id)
        grouped_by_student.setdefault(key, []).append((correct, incorrect, date))

    # Prepare table data (only first attempt per student)
    data = [["Ism Familiya", "Test", "To'g'ri", "Noto'g'ri", "Vaqti", "Urinishlar"]]
    temp_data = []
    for (student_name, username, tg_id), attempts in grouped_by_student.items():
        if attempts:
            correct, incorrect, date = attempts[0]
            temp_data.append([student_name, test_id, str(correct), str(incorrect), str(date), "1"])
    
    # Sort by correct count in descending order
    temp_data.sort(key=lambda x: int(x[2]), reverse=True)
    data.extend(temp_data)

    # create PDF with table and colored rows
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10*mm, rightMargin=10*mm, topMargin=15*mm, bottomMargin=15*mm)
    elements = []
    styles = getSampleStyleSheet()
    title_text = Paragraph(f"Test natijalari: {test[0][0]} (ID: {test_id})", styles['Heading2'])
    elements.append(title_text)
    elements.append(Spacer(1, 6*mm))
    # Space for image
    elements.append(Spacer(1, 30*mm))

    col_widths = [40*mm, 30*mm, 18*mm, 18*mm, 35*mm, 18*mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Build styles with conditional coloring for each row
    styles_list = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('ALIGN',(0,1),(1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),4),
        ('RIGHTPADDING',(0,0),(-1,-1),4),
    ]
    
    # Add row colors based on correct count
    for row_idx in range(1, len(data)):
        correct_count = int(data[row_idx][2])
        if correct_count <= 15:
            bg_color = colors.HexColor('#FF5555')  # Bright red
        elif 16 <= correct_count <= 24:
            bg_color = colors.HexColor('#FFFF88')  # Bright yellow
        else:  # 25-30
            bg_color = colors.HexColor('#55FF55')  # Bright green
        
        styles_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
        styles_list.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.black))
        styles_list.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica'))
        styles_list.append(('FONTSIZE', (0, row_idx), (-1, row_idx), 9))
    
    table.setStyle(TableStyle(styles_list))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    bot.send_document(call.message.chat.id, (f"results_{test_id}.pdf", buf))

@bot.callback_query_handler(func=lambda c: c.data == "back_admin")
def back_admin_callback(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    bot.send_message(call.message.chat.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and "(" in m.text and ")" in m.text and m.text != "⬅️ Orqaga")
def admin_view_results(message):
    # IMPORTANT: Skip ALL homework-related and quiz-related messages
    # Skip messages that start with special emojis (homework-related, quiz-related)
    if message.text.startswith("🗑") or message.text.startswith("📊") or message.text.startswith("❌"):
        return
    
    # Skip if user is in homework-related or quiz-related state
    if message.chat.id in user_state:
        state = user_state.get(message.chat.id, {})
        if state.get("step") in ["select_homework_for_results", "delete_homework", "homework_admin_menu", "delete_quiz", "quiz_menu"]:
            return
    
    # Check if this is a homework test BEFORE processing
    test_id = message.text.split("(")[-1].replace(")", "").strip()
    
    # First check if it's a homework test by ID format (5 digits) or database
    if len(test_id) == 5 and test_id.isdigit():
        # Likely a homework ID, check database
        test = query_db("SELECT test_name, is_homework FROM tests WHERE test_id = ?", (test_id,), fetch=True)
        if test:
            is_homework = test[0][1] if test else False
            if is_homework:
                return  # Skip homework tests
    
    # For non-homework tests, check database
    test = query_db("SELECT test_name, is_homework FROM tests WHERE test_id = ?", (test_id,), fetch=True)
    if not test:
        return
    
    # Skip homework tests (they're handled in homework_handlers.py)
    is_homework = test[0][1] if test else False
    if is_homework:
        return
    
    results = query_db("SELECT student_name, username, tg_id, correct_count, incorrect_count, date FROM results WHERE test_id = ? ORDER BY id ASC", (test_id,), fetch=True)
    if not results:
        bot.send_message(message.chat.id, f"📭 Bu testni hali hech kim ishlamagan.\n🆔 {test_id}")
        return
    
    # Build table and generate PDF to send to admin
    grouped_by_student = {}
    for r in results:
        student_name, username, tg_id, correct, incorrect, date = r
        key = (student_name, username, tg_id)
        grouped_by_student.setdefault(key, []).append((correct, incorrect, date))

    # Prepare table data (only first attempt per student)
    data = [["Ism Familiya", "Test", "To'g'ri", "Noto'g'ri", "Vaqti", "Urinishlar"]]
    temp_data = []
    for (student_name, username, tg_id), attempts in grouped_by_student.items():
        if attempts:
            correct, incorrect, date = attempts[0]
            temp_data.append([student_name, test_id, str(correct), str(incorrect), str(date), "1"])
    
    # Sort by correct count in descending order
    temp_data.sort(key=lambda x: int(x[2]), reverse=True)
    data.extend(temp_data)

    # create PDF with table and colored rows
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10*mm, rightMargin=10*mm, topMargin=15*mm, bottomMargin=15*mm)
    elements = []
    styles = getSampleStyleSheet()
    title_text = Paragraph(f"Test natijalari: {test[0][0]} (ID: {test_id})", styles['Heading2'])
    elements.append(title_text)
    elements.append(Spacer(1, 6*mm))
    # Space for image
    elements.append(Spacer(1, 30*mm))

    col_widths = [40*mm, 30*mm, 18*mm, 18*mm, 35*mm, 18*mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Build styles with conditional coloring for each row
    styles_list = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('ALIGN',(0,1),(1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),4),
        ('RIGHTPADDING',(0,0),(-1,-1),4),
    ]
    
    # Add row colors based on correct count
    for row_idx in range(1, len(data)):
        correct_count = int(data[row_idx][2])
        if correct_count <= 15:
            bg_color = colors.HexColor('#FF5555')  # Bright red
        elif 16 <= correct_count <= 24:
            bg_color = colors.HexColor('#FFFF88')  # Bright yellow
        else:  # 25-30
            bg_color = colors.HexColor('#55FF55')  # Bright green
        
        styles_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
        styles_list.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.black))
        styles_list.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica'))
        styles_list.append(('FONTSIZE', (0, row_idx), (-1, row_idx), 9))
    
    table.setStyle(TableStyle(styles_list))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    bot.send_document(message.chat.id, (f"results_{test_id}.pdf", buf))
def go_back(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
    else:
        from utils import user_main_menu
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    user_state.pop(message.chat.id, None)


# ============= BLOKLASH TIZIMI =============

def is_user_blocked(chat_id):
    """Foydalanuvchi bloklangan yoki yo'q"""
    result = query_db(
        "SELECT id FROM blocked_users WHERE chat_id = ?",
        (str(chat_id),),
        fetch=True
    )
    return bool(result)

@bot.message_handler(func=lambda m: m.text == "🚫 Bloklangan foydalanuvchilar" and m.from_user.id in ADMIN_IDS)
def show_blocked_users(message):
    """Bloklangan foydalanuvchilar ro'yxati"""
    blocked = query_db(
        "SELECT chat_id, username, student_name, blocked_at, reason FROM blocked_users ORDER BY blocked_at DESC",
        fetch=True
    ) or []
    
    if not blocked:
        bot.send_message(message.chat.id, "✅ Bloklangan foydalanuvchilar yo'q", reply_markup=admin_main_menu())
        return
    
    text = "🚫 <b>Bloklangan Foydalanuvchilar</b>\n\n"
    
    kb = types.InlineKeyboardMarkup()
    
    for idx, (chat_id, username, student_name, blocked_at, reason) in enumerate(blocked, 1):
        display_name = student_name or username or chat_id
        text += f"{idx}. 👤 {display_name}\n"
        text += f"   🔒 Bloklandi: {blocked_at}\n"
        if reason:
            text += f"   📝 Sabab: {reason}\n"
        text += "\n"
        
        kb.add(types.InlineKeyboardButton(
            f"🔓 Ochish - {display_name[:10]}", 
            callback_data=f"unblock_user:{chat_id}"
        ))
    
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)
    user_state[message.chat.id] = {"step": "blocked_list"}

@bot.callback_query_handler(func=lambda call: call.data.startswith("unblock_user:"))
def unblock_user_callback(call):
    """Foydalanuvchini blokdan ochish"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    chat_id = call.data.split(":", 1)[1]
    
    blocked_info = query_db(
        "SELECT username, student_name FROM blocked_users WHERE chat_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not blocked_info:
        bot.answer_callback_query(call.id, "❌ Bu foydalanuvchi bloklangan emas!", show_alert=True)
        return
    
    username, student_name = blocked_info[0]
    display_name = student_name or username or chat_id
    
    query_db("DELETE FROM blocked_users WHERE chat_id = ?", (chat_id,))
    
    # Foydalanuvchiga bildirishnoma
    try:
        bot.send_message(
            int(chat_id),
            "✅ <b>Xush kelibsiz!</b>\n\nSiz qora ro'yxatdan chiqarildingiz. Endi botdan foydalana olasiz.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    bot.answer_callback_query(call.id, f"✅ @{display_name} blokdan ochildi!", show_alert=True)
    show_blocked_users(call.message)

@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilarni boshqarish" and m.from_user.id in ADMIN_IDS)
def manage_users_menu(message):
    """Foydalanuvchilarni boshqarish menyusi"""
    users = query_db(
        "SELECT chat_id, student_name, username FROM users ORDER BY student_name ASC",
        fetch=True
    ) or []
    
    if not users:
        bot.send_message(message.chat.id, "📭 Foydalanuvchilar yo'q", reply_markup=admin_main_menu())
        return
    
    kb = types.InlineKeyboardMarkup()
    
    for chat_id, student_name, username in users[:20]:  # Birinchi 20 ta
        display = f"{student_name or username or chat_id}"
        is_blocked = is_user_blocked(chat_id)
        button_text = f"{'🔒' if is_blocked else '✅'} {display[:20]}"
        kb.add(types.InlineKeyboardButton(button_text, callback_data=f"user_action:{chat_id}"))
    
    if len(users) > 20:
        kb.add(types.InlineKeyboardButton(f"Yana {len(users) - 20} ta...", callback_data="more_users"))
    
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
    
    text = f"👥 <b>Foydalanuvchilarni Boshqarish</b>\n\nJami: {len(users)} ta\n\nFoydalanuvchini tanlang:"
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)
    user_state[message.chat.id] = {"step": "users_list"}

@bot.callback_query_handler(func=lambda call: call.data.startswith("user_action:"))
def user_action_menu(call):
    """Foydalanuvchi bilan amallar"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    chat_id = call.data.split(":", 1)[1]
    
    user_info = query_db(
        "SELECT student_name, username, balance FROM users WHERE chat_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not user_info:
        bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    student_name, username, balance = user_info[0]
    is_blocked = is_user_blocked(chat_id)
    
    text = f"👤 <b>Foydalanuvchi: {student_name}</b>\n"
    text += f"📝 Username: @{username or 'yo\'q'}\n"
    text += f"💰 Balans: {balance} som\n"
    text += f"🔒 Status: {'Bloklangan' if is_blocked else 'Aktiv'}\n\n"
    text += "Amal tanlang:"
    
    kb = types.InlineKeyboardMarkup()
    
    if is_blocked:
        kb.add(types.InlineKeyboardButton("🔓 Blokdan ochish", callback_data=f"unblock_user:{chat_id}"))
    else:
        kb.add(types.InlineKeyboardButton(
            "🔒 Bloklash", 
            callback_data=f"confirm_block:{chat_id}"
        ))
    
    kb.add(types.InlineKeyboardButton("💰 Balans o'zgartirish", callback_data=f"change_balance:{chat_id}"))
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_users_back"))
    
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_block:"))
def confirm_block_user(call):
    """Bloklashni tasdiqlash"""
    if call.from_user.id not in ADMIN_IDS:
        return
    
    chat_id = call.data.split(":", 1)[1]
    
    user_info = query_db(
        "SELECT student_name, username FROM users WHERE chat_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not user_info:
        bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    student_name, username = user_info[0]
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Ha, bloklash", callback_data=f"block_confirm_yes:{chat_id}"))
    kb.add(types.InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data=f"cancel_block:{chat_id}"))
    
    text = f"⚠️ <b>Tasdiqlash</b>\n\n{student_name}ni bloklashga ishonchingiz komilmi?"
    
    bot.edit_message_text(text, call.from_user.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("block_confirm_yes:"))
def block_user_confirmed(call):
    """Foydalanuvchini bloklash - tasdiqlandi"""
    if call.from_user.id not in ADMIN_IDS:
        return
    
    chat_id = call.data.split(":", 1)[1]
    
    user_info = query_db(
        "SELECT student_name, username FROM users WHERE chat_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not user_info:
        bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    student_name, username = user_info[0]
    
    # Bloklash
    query_db(
        "INSERT OR REPLACE INTO blocked_users (chat_id, username, student_name, blocked_at, blocked_by, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (
            chat_id,
            username,
            student_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(call.from_user.id),
            "Admin tomonidan bloklandi"
        )
    )
    
    # Bloklangan foydalanuvchiga bildirishnoma
    try:
        bot.send_message(
            int(chat_id),
            "❌ <b>Qora ro'yxatdagi shaxsiz</b>\n\nSiz qora ro'yxatga kiritildingiz.\nAdmin bilan bog'lanib qaytadan urinib ko'ring!.\n\n@math_3322",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    # Message ni o'chirish va callback javobini berish
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
    except Exception:
        pass
    
    bot.answer_callback_query(call.id, f"✅ {student_name} bloklandi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_block:"))
def cancel_block_callback(call):
    """Bloklashni bekor qilish"""
    if call.from_user.id not in ADMIN_IDS:
        return
    
    chat_id = call.data.split(":", 1)[1]
    
    # Message ni o'chirish
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
    except Exception:
        pass
    
    bot.answer_callback_query(call.id, "❌ Bekor qilindi", show_alert=False)

@bot.callback_query_handler(func=lambda call: call.data in ("admin_back", "admin_users_back"))
def admin_back_callback(call):
    """Admin orqaga"""
    if call.from_user.id not in ADMIN_IDS:
        return
    
    bot.send_message(call.from_user.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
    bot.answer_callback_query(call.id)
# ============= TEZKOR BLOKLASH =============

@bot.callback_query_handler(func=lambda call: call.data.startswith("quick_block:"))
def quick_block_user(call):
    """Xabar tagidagi tugmadan tezkor bloklash"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    try:
        parts = call.data.split(":")
        if len(parts) < 2:
            bot.answer_callback_query(call.id, "❌ Xatolik!", show_alert=True)
            return
        
        user_id = parts[1]
        
        # User info olish
        user_info = query_db(
            "SELECT student_name, username FROM users WHERE chat_id = ?",
            (user_id,),
            fetch=True
        )
        
        if not user_info:
            bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi!", show_alert=True)
            return
        
        student_name, username = user_info[0]
        
        # Bloklash
        query_db(
            "INSERT OR REPLACE INTO blocked_users (chat_id, username, student_name, blocked_at, blocked_by, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                username,
                student_name,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(call.from_user.id),
                "Test/Uyga vazifa natijasidan tezkor bloklash"
            )
        )
        
        # Bloklangan foydalanuvchiga bildirishnoma
        try:
            bot.send_message(
                int(user_id),
                "❌ <b>Qora ro'yxatdagi shaxsiz</b>\n\nSiz qora ro'yxatga kiritildingiz. Admin bilan bog'lanish uchun urinib ko'ring.\n\n@math_3322",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        # Message ni edit qilish - bloklash tugmasi o'chirilsin
        try:
            bot.edit_message_reply_markup(call.from_user.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        
        bot.answer_callback_query(call.id, f"✅ {student_name} bloklandi!", show_alert=True)
    except Exception as e:
        logger.exception(f"Quick block error: {e}")
        bot.answer_callback_query(call.id, f"❌ Xatolik: {str(e)[:50]}", show_alert=True)

# ============= KARTA BOSHQARISH =============

def get_db_id_by_visible_id(visible_id):
    """Ko'rinadigan ID (1, 2, 3...) ni DB ID ga o'girish"""
    active_cards = query_db(
        "SELECT id FROM bot_cards WHERE is_active = 1 ORDER BY id ASC",
        fetch=True
    ) or []
    
    if visible_id <= 0 or visible_id > len(active_cards):
        return None
    
    return active_cards[visible_id - 1][0]  # visible_id 1-based, list 0-based

@bot.message_handler(func=lambda m: m.text == "💳 Kartalarni boshqarish" and m.from_user.id in ADMIN_IDS)
def manage_bot_cards_menu(message):
    """Bot kartalarini boshqarish menyusi"""
    cards = query_db(
        "SELECT id, card_number, card_owner, bank_name, is_active FROM bot_cards ORDER BY is_active DESC",
        fetch=True
    ) or []
    
    if not cards:
        text = "📭 <b>Karta raqamlar yo'q</b>\n\n"
        text += "Admin paneldan karta raqam qo'shishingiz kerak.\n"
        text += "/add_card XXXXXX XXXXXX XXXXXX XXXXXX Egasi Bank"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())
        return
    
    text = "💳 <b>Bot Kartalar</b>\n\n"
    
    # Faol kartalarni alohida ko'rsatish
    active_cards = [(idx, card_id, card_num, owner, bank) for idx, (card_id, card_num, owner, bank, is_active) in enumerate(cards, 1) if is_active]
    inactive_cards = [(card_id, card_num, owner, bank, is_active) for card_id, card_num, owner, bank, is_active in cards if not is_active]
    
    # Faol kartalarni ko'rinadigan ID bilan ko'rsatish
    if active_cards:
        text += "✅ <b>Faol Kartalar:</b>\n\n"
        for visible_id, card_id, card_num, owner, bank in active_cards:
            text += f"🆔 <b>Karta ID: {visible_id}</b>\n"
            text += f"🏦 {bank}\n"
            text += f"💳 {card_num}\n"
            text += f"👤 {owner}\n"
            

    
    # Faol emas kartalarni ko'rsatish
    if inactive_cards:
        text += "❌ <b>Faol Emas Kartalar:</b>\n\n"
        for card_id, card_num, owner, bank, is_active in inactive_cards:
            text += f"🆔 <b>Karta ID: {card_id}</b>\n"
            text += f"🏦 {bank}\n"
            text += f"💳 {card_num}\n"
            text += f"👤 {owner}\n"
            

    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())

@bot.message_handler(commands=['add_card'])
def add_card_command(message):
    """Yangi karta qo'shish: /add_card XXXXXX XXXXXX XXXXXX XXXXXX Egasi Bank"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 6:
            bot.send_message(
                message.chat.id,
                "❌ Noto'g'ri format!\n\n"
                "Format: /add_card XXXXXX XXXXXX XXXXXX XXXXXX Egasi BankNomi\n"
                "Misol: /add_card 9860 1234 5678 9012 Ali Uzbqazo'q",
                parse_mode="HTML"
            )
            return
        
        card_parts = parts[1:5]
        card_number = " ".join(card_parts)
        card_owner = " ".join(parts[5:-1])
        bank_name = parts[-1]
        
        query_db(
            "INSERT INTO bot_cards (card_number, card_owner, bank_name) VALUES (?, ?, ?)",
            (card_number, card_owner, bank_name)
        )
        
        # Faol kartalar sonini hisoblash (ko'rinadigan ID uchun)
        active_count = query_db(
            "SELECT COUNT(*) FROM bot_cards WHERE is_active = 1",
            fetch=True
        )
        visible_id = active_count[0][0] if active_count else 1
        
        text = f"✅ <b>Karta qo'shildi!</b>\n\n"
        text += f"🆔 <b>Karta ID:</b> {visible_id}\n"
        text += f"🏦 Bank: {bank_name}\n"
        text += f"💳 Karta: {card_number}\n"
        text += f"👤 Egasi: {card_owner}"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())
    except Exception as e:
        logger.exception(f"Add card error: {e}")
        bot.send_message(message.chat.id, f"❌ Xato: {str(e)}", reply_markup=admin_main_menu())

@bot.message_handler(commands=['toggle_card'])
def toggle_card_status(message):
    """Karta statusini o'zgartirish: /toggle_card ID (ko'rinadigan ID yoki DB ID)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Karta ID kerak: /toggle_card ID")
            return
        
        input_id = int(parts[1])
        
        # Avval ko'rinadigan ID sifatida tekshirish
        db_id = get_db_id_by_visible_id(input_id)
        
        # Agar ko'rinadigan ID bo'lmasa, DB ID sifatida tekshirish
        if db_id is None:
            db_id = input_id
        
        card = query_db(
            "SELECT is_active, card_number FROM bot_cards WHERE id = ?",
            (db_id,),
            fetch=True
        )
        
        if not card:
            bot.send_message(message.chat.id, "❌ Karta topilmadi")
            return
        
        current_status = card[0][0]
        card_num = card[0][1]
        new_status = 0 if current_status == 1 else 1
        
        query_db("UPDATE bot_cards SET is_active = ? WHERE id = ?", (new_status, db_id))
        
        status_text = "✅ Faol" if new_status else "❌ Faol emas"
        text = f"✅ <b>Karta {status_text} bo'ldi</b>\n\n"
        text += f"💳 Karta: {card_num}"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())
    except Exception as e:
        logger.exception(f"Toggle card error: {e}")
        bot.send_message(message.chat.id, f"❌ Xato: {str(e)}", reply_markup=admin_main_menu())

@bot.message_handler(commands=['delete_card'])
def delete_card_command(message):
    """Kartani o'chirish: /delete_card ID (ko'rinadigan ID yoki DB ID)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Karta ID kerak: /delete_card ID")
            return
        
        input_id = int(parts[1])
        
        # Avval ko'rinadigan ID sifatida tekshirish
        db_id = get_db_id_by_visible_id(input_id)
        
        # Agar ko'rinadigan ID bo'lmasa, DB ID sifatida tekshirish
        if db_id is None:
            db_id = input_id
        
        card = query_db(
            "SELECT card_number FROM bot_cards WHERE id = ?",
            (db_id,),
            fetch=True
        )
        
        if not card:
            bot.send_message(message.chat.id, "❌ Karta topilmadi")
            return
        
        query_db("DELETE FROM bot_cards WHERE id = ?", (db_id,))
        
        text = f"✅ <b>Karta o'chirildi</b>\n\n"
        text += f"💳 Karta: {card[0][0]}"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())
    except Exception as e:
        logger.exception(f"Delete card error: {e}")
        bot.send_message(message.chat.id, f"❌ Xato: {str(e)}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "✅ Active users" and m.from_user.id in ADMIN_IDS)
def show_active_users(message):
    """Active users ro'yxatini ko'rsatish"""
    try:
        # Faol obunachilarni olish
        active_users = query_db(
            """SELECT s.user_id, s.username, s.student_name, s.start_date, s.end_date, s.payment_id
               FROM subscriptions s
               WHERE s.is_active = 1
               ORDER BY s.end_date DESC""",
            fetch=True
        ) or []
        
        if not active_users:
            bot.send_message(message.chat.id, "📭 Hozircha faol obunachilar yo'q.", reply_markup=admin_main_menu())
            return
        
        text = "✅ <b>Faol obunachilar:</b>\n\n"
        kb = types.InlineKeyboardMarkup()
        
        for user_id, username, student_name, start_date, end_date, payment_id in active_users:
            user_display = f"@{username}" if username else f"tg:{user_id}"
            end_date_short = end_date[:10] if end_date else "Noma'lum"
            
            text += f"👤 <b>{student_name or 'Noma\'lum'}</b> ({user_display})\n"
            text += f"   📅 Tugash: {end_date_short}\n\n"
            
            # Har bir user uchun "Obunani faolsizlantirish" tugmasi
            kb.add(types.InlineKeyboardButton(
                text=f"🚫 {student_name or user_id}",
                callback_data=f"deactivate_subscription:{user_id}"
            ))
        
        kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
        
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.exception(f"Show active users error: {e}")
        bot.send_message(message.chat.id, f"❌ Xato: {str(e)}", reply_markup=admin_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith("deactivate_subscription:"))
def deactivate_subscription_callback(call):
    """Obunani faolsizlantirish"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    try:
        user_id = call.data.split(":")[1]
        
        # Obunani faolsizlantirish
        query_db(
            "UPDATE subscriptions SET is_active = 0 WHERE user_id = ?",
            (user_id,)
        )
        
        # Foydalanuvchiga xabar yuborish
        try:
            user_info = query_db(
                "SELECT student_name, username FROM subscriptions WHERE user_id = ?",
                (user_id,),
                fetch=True
            )
            
            if user_info:
                student_name = user_info[0][0] or "Foydalanuvchi"
                text_user = "❌ <b>Sizning obunangiz bekor qilindi!</b>\n\n"
                text_user += "Admin tomonidan obunangiz faolsizlantirildi.\n"
                text_user += "Qayta obuna bo'lish uchun to'lov qiling."
                
                bot.send_message(int(user_id), text_user, parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            logger.exception(f"User ga xabar yuborishda xatolik: {e}")
        
        # Admin ga xabar
        student_name = user_info[0][0] if user_info else "Noma'lum"
        text = f"✅ <b>Obuna faolsizlantirildi</b>\n\n"
        text += f"👤 Foydalanuvchi: {student_name}\n"
        text += f"🆔 ID: {user_id}"
        
        bot.send_message(call.from_user.id, text, parse_mode="HTML")
        
        # Ro'yxatni yangilash - yangi xabar yuborish
        active_users = query_db(
            """SELECT s.user_id, s.username, s.student_name, s.start_date, s.end_date, s.payment_id
               FROM subscriptions s
               WHERE s.is_active = 1
               ORDER BY s.end_date DESC""",
            fetch=True
        ) or []
        
        if not active_users:
            bot.send_message(call.from_user.id, "📭 Hozircha faol obunachilar yo'q.", reply_markup=admin_main_menu())
            return
        
        text_list = "✅ <b>Faol obunachilar:</b>\n\n"
        kb = types.InlineKeyboardMarkup()
        
        for uid, username, s_name, start_date, end_date, payment_id in active_users:
            user_display = f"@{username}" if username else f"tg:{uid}"
            end_date_short = end_date[:10] if end_date else "Noma'lum"
            
            text_list += f"👤 <b>{s_name or 'Noma\'lum'}</b> ({user_display})\n"
            text_list += f"   📅 Tugash: {end_date_short}\n\n"
            
            kb.add(types.InlineKeyboardButton(
                text=f"🚫 {s_name or uid}",
                callback_data=f"deactivate_subscription:{uid}"
            ))
        
        kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
        
        bot.send_message(call.from_user.id, text_list, parse_mode="HTML", reply_markup=kb)
        
    except Exception as e:
        logger.exception(f"Deactivate subscription error: {e}")
        bot.send_message(call.from_user.id, f"❌ Xato: {str(e)}", reply_markup=admin_main_menu())