import re
import logging
from datetime import datetime
from telebot import types
from config import bot, ADMIN_IDS, user_state
from database import query_db, load_profile
from utils import user_main_menu, admin_main_menu, back_button, generate_homework_id

logger = logging.getLogger(__name__)

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa" and m.from_user and m.from_user.id not in ADMIN_IDS)
def user_homework_menu(message):
    try:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("📊 Uyga vazifa natijalari", "📝 Uyga vazifa topshirish")
        kb.add("⬅️ Orqaga")
        bot.send_message(message.chat.id, "📝 Uyga vazifa bo'limi:", reply_markup=kb)
        user_state[message.chat.id] = {"step": "homework_menu"}
    except Exception as e:
        logger.exception(f"Error in user_homework_menu: {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa" and m.from_user and m.from_user.id in ADMIN_IDS)
def add_homework_start(message):
    bot.send_message(message.chat.id, "📚 Uyga vazifa nomini kiriting:", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "get_homework_name"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_homework_name")
def get_homework_name(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        from handlers.admin_handlers import go_back
        go_back(message)
        return
    
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ Uyga vazifa nomi bo'sh bo'lmasligi kerak.")
        return
    
    user_state[message.chat.id]["homework_name"] = name
    user_state[message.chat.id]["step"] = "get_homework_answers"
    bot.send_message(message.chat.id, "📝 To'g'ri javoblarni kiriting:\nFormat: <b>1a2a3a4b5c...30a</b> (30 ta javob)", parse_mode="HTML", reply_markup=back_button())

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_homework_answers")
def save_homework(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        from handlers.admin_handlers import go_back
        go_back(message)
        return
    
    data = user_state.get(message.chat.id, {})
    text = message.text.strip()
    
    pattern = r'(\d+)([a-eA-E])'
    matches = re.findall(pattern, text)
    
    if len(matches) < 30:
        bot.send_message(message.chat.id, f"❌ Kamida 30 ta javob kiriting. Hozir: {len(matches)} ta\nFormat: 1a2a3a4b5c...30a")
        return
    
    if len(matches) > 30:
        bot.send_message(message.chat.id, f"❌ Maksimal 30 ta javob. Hozir: {len(matches)} ta\nFaqat birinchi 30 tasi qabul qilinadi.")
        matches = matches[:30]
    
    answers_dict = {}
    for num_str, letter in matches:
        num = int(num_str)
        if 1 <= num <= 30:
            answers_dict[num] = letter.lower()
    
    if len(answers_dict) < 30:
        missing = [i for i in range(1, 31) if i not in answers_dict]
        bot.send_message(message.chat.id, f"❌ Quyidagi savollar uchun javob topilmadi: {', '.join(map(str, missing[:10]))}{'...' if len(missing) > 10 else ''}\nBarcha 30 ta savol uchun javob kiriting.")
        return
    
    correct_answers = ''.join([answers_dict[i] for i in range(1, 31)])
    homework_id = generate_homework_id()
    
    query_db(
        "INSERT OR REPLACE INTO tests (test_id, test_name, correct_answers, created_at, is_homework) VALUES (?, ?, ?, ?, ?)",
        (homework_id, data.get("homework_name"), correct_answers, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1)
    )
    
    user_state.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Uyga vazifa saqlandi!\n🆔 Test ID: <b>{homework_id}</b>\n📘 Nomi: {data.get('homework_name')}\n📊 Javoblar soni: 30 ta",
        parse_mode="HTML",
        reply_markup=admin_main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa boshqaruvi" and m.from_user.id in ADMIN_IDS)
def admin_homework_menu(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Uyga vazifa qo'shish", "📊 Uyga vazifa natijalari")
    kb.add("🗑 Uyga vazifa o'chirish", "⬅️ Orqaga")
    bot.send_message(message.chat.id, "📝 Uyga vazifa boshqaruvi:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "homework_admin_menu"}

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and m.chat.id in user_state and user_state[m.chat.id].get("step") == "homework_admin_menu")
def back_from_homework_admin_menu(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    user_state.pop(message.chat.id, None)
    from handlers.admin_handlers import go_back
    go_back(message)

@bot.message_handler(func=lambda m: m.text == "➕ Uyga vazifa qo'shish" and m.from_user.id in ADMIN_IDS)
def admin_add_homework_start(message):
    bot.send_message(message.chat.id, "📚 Uyga vazifa nomini kiriting:", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "get_homework_name"}

@bot.message_handler(func=lambda m: m.text == "📊 Uyga vazifa natijalari" and m.from_user.id in ADMIN_IDS)
def admin_show_homework_results(message):
    homeworks = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 1 ORDER BY created_at DESC", fetch=True) or []
    
    if not homeworks:
        bot.send_message(message.chat.id, "📭 Hozircha uyga vazifalar mavjud emas.", reply_markup=admin_main_menu())
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for hw_id, hw_name in homeworks:
        kb.add(f"📊 {hw_name} ({hw_id})")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "Natijalarini ko'rish uchun uyga vazifani tanlang:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "select_homework_for_results"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "select_homework_for_results")
def show_homework_results_details(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        admin_homework_menu(message)
        return
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.search(r'\((\d+)\)', message.text)
    if not match:
        bot.send_message(message.chat.id, "❌ Noto'g'ri tanlov.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    homework_id = match.group(1)
    
    results = query_db(
        "SELECT student_name, username, tg_id, correct_count, incorrect_count, date FROM results WHERE test_id = ? ORDER BY date DESC",
        (homework_id,),
        fetch=True
    ) or []
    
    if not results:
        bot.send_message(message.chat.id, f"📭 Bu uyga vazifani hali hech kim ishlamagan.\n🆔 {homework_id}", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    test_info = query_db("SELECT test_name FROM tests WHERE test_id = ?", (homework_id,), fetch=True)
    test_name = test_info[0][0] if test_info else "Noma'lum"
    
    text = f"📊 <b>Uyga vazifa natijalari</b>\n"
    text += f"📘 Nomi: {test_name}\n"
    text += f"🆔 ID: {homework_id}\n\n"
    
    user_stats = {}
    for r in results:
        student_name, username, tg_id, correct, incorrect, date = r
        key = (student_name, username, tg_id)
        if key not in user_stats:
            user_stats[key] = {"correct": 0, "incorrect": 0, "attempts": 0, "dates": []}
        user_stats[key]["correct"] += correct
        user_stats[key]["incorrect"] += incorrect
        user_stats[key]["attempts"] += 1
        user_stats[key]["dates"].append(date)
    
    for (student_name, username, tg_id), stats in sorted(user_stats.items(), key=lambda x: x[1]["correct"], reverse=True):
        user_display = f"@{username}" if username else f"tg:{tg_id}"
        total = stats["correct"] + stats["incorrect"]
        percentage = (stats["correct"] / total * 100) if total > 0 else 0
        
        text += f"🧑‍🎓 <b>{student_name}</b> ({user_display})\n"
        text += f"  ✅ To'g'ri: {stats['correct']} | ❌ Xato: {stats['incorrect']} | 📊 {percentage:.1f}%\n"
        text += f"  📝 Topshirilgan: {stats['attempts']} marta\n"
        text += f"  🕓 Oxirgi marta: {stats['dates'][0]}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=admin_main_menu())
    user_state.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "🗑 Uyga vazifa o'chirish" and m.from_user.id in ADMIN_IDS)
def admin_delete_homework_start(message):
    homeworks = query_db("SELECT test_id, test_name FROM tests WHERE is_homework = 1 ORDER BY created_at DESC", fetch=True) or []
    
    if not homeworks:
        bot.send_message(message.chat.id, "📭 O'chirish uchun uyga vazifalar yo'q.", reply_markup=admin_main_menu())
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for hw_id, hw_name in homeworks:
        kb.add(f"🗑 {hw_name} ({hw_id})")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "O'chirish uchun uyga vazifani tanlang:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "delete_homework"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "delete_homework")
def admin_delete_selected_homework(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        admin_homework_menu(message)
        return
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.search(r'\((\d+)\)', message.text)
    if not match:
        bot.send_message(message.chat.id, "❌ Noto'g'ri tanlov.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    homework_id = match.group(1)
    
    test = query_db("SELECT test_name FROM tests WHERE test_id = ? AND is_homework = 1", (homework_id,), fetch=True)
    if not test:
        bot.send_message(message.chat.id, "❌ Bunday uyga vazifa topilmadi yoki uyga vazifa emas.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    query_db("DELETE FROM tests WHERE test_id = ? AND is_homework = 1", (homework_id,))
    query_db("DELETE FROM results WHERE test_id = ?", (homework_id,))
    query_db("DELETE FROM videos WHERE test_id = ?", (homework_id,))
    
    user_state.pop(message.chat.id, None)
    bot.send_message(message.chat.id, f"✅ Uyga vazifa o'chirildi!\n🆔 {homework_id}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and m.chat.id in user_state and user_state[m.chat.id].get("step") == "homework_menu")
def back_from_homework_menu(message):
    user_state.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa topshirish")
def submit_homework_start(message):
    if message.from_user.id in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "🆔 Uyga vazifa ID va javoblaringizni kiriting:\nFormat: <b>12345 1a2a3a4b5c...30a</b>\nMasalan: <b>12345 1a2b3c4d5e...30a</b>", parse_mode="HTML", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "submit_homework"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "submit_homework")
def process_homework_answers(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        user_homework_menu(message)
        return
    
    text = message.text.strip()
    
    parts = text.split(None, 1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Noto'g'ri format. Format: <b>ID 1a2a3a4b5c...30a</b>\nMasalan: <b>12345 1a2b3c4d5e...30a</b>", parse_mode="HTML")
        return
    
    homework_id = parts[0].strip()
    answers_text = parts[1].strip()
    
    test = query_db("SELECT test_name, correct_answers FROM tests WHERE test_id = ?", (homework_id,), fetch=True)
    if not test:
        bot.send_message(message.chat.id, "❌ Bunday uyga vazifa topilmadi. ID ni tekshirib qayta kiriting.")
        return
    
    homework_name = test[0][0]
    correct_answers_str = test[0][1]
    
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)
    existing_result = query_db(
        "SELECT COUNT(*) FROM results WHERE (username = ? OR tg_id = ?) AND test_id = ?",
        (username, tg_id, homework_id),
        fetch=True
    )
    if existing_result and existing_result[0][0] > 0:
        bot.send_message(
            message.chat.id,
            f"⚠️ <b>Siz oldin bu uyga vazifani ishlagansiz!</b>\n\n🆔 ID: {homework_id}\n📘 Nomi: {homework_name}\n\nUyga vazifani faqat bir marta topshirish mumkin.",
            parse_mode="HTML",
            reply_markup=user_main_menu()
        )
        user_state.pop(message.chat.id, None)
        return
    
    pattern = r'(\d+)([a-eA-E])'
    matches = re.findall(pattern, answers_text)
    
    if len(matches) < 30:
        bot.send_message(message.chat.id, f"❌ Kamida 30 ta javob kiriting. Hozir: {len(matches)} ta\nFormat: 1a2a3a4b5c...30a")
        return
    
    if len(matches) > 30:
        bot.send_message(message.chat.id, f"⚠️ 30 tadan ko'p javob kiritdingiz. Faqat birinchi 30 tasi qabul qilinadi.")
        matches = matches[:30]
    
    user_answers_dict = {}
    for num_str, letter in matches:
        num = int(num_str)
        if 1 <= num <= 30:
            user_answers_dict[num] = letter.lower()
    
    if len(user_answers_dict) < 30:
        missing = [i for i in range(1, 31) if i not in user_answers_dict]
        bot.send_message(message.chat.id, f"❌ Quyidagi savollar uchun javob topilmadi: {', '.join(map(str, missing[:10]))}{'...' if len(missing) > 10 else ''}\nBarcha 30 ta savol uchun javob kiriting.")
        return
    
    user_answers = ''.join([user_answers_dict[i] for i in range(1, 31)])
    correct_answers = correct_answers_str
    
    total_questions = len(correct_answers)
    correct = 0
    incorrect_details = []
    
    for i in range(min(total_questions, len(user_answers))):
        ua = user_answers[i] if i < len(user_answers) else None
        ca = correct_answers[i] if i < len(correct_answers) else None
        if ua is not None and ca is not None and ua == ca:
            correct += 1
        else:
            incorrect_details.append((i + 1, ua))
    
    incorrect = total_questions - correct
    
    student_name = load_profile(message.chat.id) or "Unknown"
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)
    
    query_db(
        "INSERT INTO results (student_name, username, tg_id, test_id, correct_count, incorrect_count, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (student_name, username, tg_id, homework_id, correct, incorrect, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    
    result_text = f"📊 <b>Uyga vazifa natijangiz:</b>\n"
    result_text += f"🆔 ID: {homework_id}\n"
    result_text += f"📘 Nomi: {homework_name}\n"
    result_text += f"✅ To'g'ri javoblar: {correct} ta\n"
    result_text += f"❌ Xato javoblar: {incorrect} ta\n"
    
    if incorrect_details:
        result_text += f"\n❗ <b>Xato javoblar:</b>\n"
        for qnum, ua in incorrect_details:
            ua_display = ua.upper() if ua else "—"
            result_text += f"{qnum}-savol: Siz belgilagan javob <b>{ua_display}</b> ❌\n"
    
    bot.send_message(message.chat.id, result_text, parse_mode="HTML", reply_markup=user_main_menu())
    
    from config import ADMIN_IDS
    user_display = f"@{username}" if username else f"tg:{tg_id}"
    admin_caption = f"📥 Uyga vazifa topshirildi:\n🧑‍🎓 {student_name}\n🆔 {homework_id}\n✅ {correct} | ❌ {incorrect}\n{user_display}"
    
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, admin_caption)
        except Exception:
            pass
    
    user_state.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "📊 Uyga vazifa natijalari")
def show_homework_results(message):
    if message.from_user.id in ADMIN_IDS:
        return
    
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)
    
    all_results = query_db(
        """SELECT r.test_id, r.correct_count, r.incorrect_count, r.date, t.is_homework
            FROM results r 
            LEFT JOIN tests t ON r.test_id = t.test_id 
            WHERE (r.username = ? OR r.tg_id = ?) 
            ORDER BY r.date DESC""",
        (username, tg_id),
        fetch=True
    ) or []
    
    results = []
    for r in all_results:
        test_id = str(r[0])
        is_homework = r[4] if len(r) > 4 else None
        is_homework_test = (is_homework == 1) or (len(test_id) == 5 and test_id.isdigit())
        if is_homework_test:
            results.append((r[0], r[1], r[2], r[3]))
    
    if not results:
        bot.send_message(message.chat.id, "📭 Siz hali uyga vazifalarni topshirmadingiz.", reply_markup=user_main_menu())
        return
    
    text = "📊 <b>Sizning uyga vazifa natijalaringiz:</b>\n\n"
    
    grouped_results = {}
    for r in results:
        test_id, correct, incorrect, date = r
        if test_id not in grouped_results:
            grouped_results[test_id] = []
        grouped_results[test_id].append((correct, incorrect, date))
    
    for test_id, attempts in grouped_results.items():
        test_name = query_db("SELECT test_name FROM tests WHERE test_id = ?", (test_id,), fetch=True)
        test_name = test_name[0][0] if test_name else "Noma'lum"
        
        text += f"<b>🆔 {test_id}</b> - {test_name}\n"
        for attempt_num, (correct, incorrect, date) in enumerate(attempts, 1):
            total = correct + incorrect
            percentage = (correct / total * 100) if total > 0 else 0
            text += f"  {attempt_num}-natijangiz: ✅ {correct} | ❌ {incorrect} | 📊 {percentage:.1f}% | 🕓 {date}\n"
        text += "\n"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=user_main_menu())

