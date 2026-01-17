import re
import logging
from datetime import datetime
from telebot import types
from config import bot, ADMIN_IDS, user_state
from database import query_db, load_profile
from utils import user_main_menu, admin_main_menu, back_button, generate_homework_id

logger = logging.getLogger(__name__)

def require_payment(message):
    """To'lov tekshiruv funksiyasi - agar to'lov qilmagan bo'lsa True qaytaradi va xabar yuboradi"""
    # Adminlar uchun ruxsat
    if message.from_user.id in ADMIN_IDS:
        return False
    
    # To'lov menyusiga ruxsat
    if message.text == "💳 To'lov":
        return False
    
    # Obunani tekshirish
    from handlers.payment_handlers import check_subscription
    sub = check_subscription(str(message.from_user.id))
    
    if not sub["active"]:
        text = "❌ <b>To'lov qilmagansiz!</b>\n\n"
        text += "Iltimos, hisobingizni to'ldiring.\n"
        text += "💰 Oylik to'lov: 15,000 so'm\n\n"
        text += "To'lov qilish uchun pastdagi tugmani bosing."
        
        # Barcha tugmalarni yopish
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
        
        # Faqat to'lov tugmasi bilan yangi keyboard
        payment_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        payment_kb.add("💳 To'lov")
        
        # Inline keyboard bilan to'lov tugmasi
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Hisobni to'ldirish", callback_data="topup_account"))
        
        bot.send_message(message.chat.id, "💳 To'lov qilish uchun tugmani bosing:", reply_markup=payment_kb)
        bot.send_message(message.chat.id, "Yoki pastdagi tugmani bosing:", reply_markup=kb)
        return True
    
    return False

# ==================== USER HANDLERS ====================

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa" and m.from_user and m.from_user.id not in ADMIN_IDS)
def user_homework_menu(message):
    if require_payment(message):
        return
    try:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("📊 Uyga vazifa natijalari", "📝 Uyga vazifa topshirish")
        kb.add("⬅️ Orqaga")
        bot.send_message(message.chat.id, "📝 Uyga vazifa bo'limi:", reply_markup=kb)

        user_state[message.chat.id] = {"step": "homework_menu"}
    except Exception as e:
        logger.exception(f"Error in user_homework_menu: {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and m.chat.id in user_state and user_state[m.chat.id].get("step") == "homework_menu")
def back_from_homework_menu(message):
    user_state.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa topshirish" and m.from_user.id not in ADMIN_IDS)
def submit_homework_start(message):
    if require_payment(message):
        return
    
    # Blok tekshirish
    from handlers.admin_handlers import is_user_blocked
    if is_user_blocked(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "❌ <b>Qora ro'yxatdagi shaxsiz</b>\n\nSiz qora ro'yxatga kiritildingiz.\nAdmin bilan bog'lanib qaytadan urinib ko'ring!.\n\n@math_3322",
            parse_mode="HTML",
            reply_markup=user_main_menu()
        )
        return
    
    bot.send_message(message.chat.id, "🆔 Uyga vazifa ID va javoblaringizni kiriting:\nFormat: <b>12345 1a2a3a4b5c...30a</b>\nMasalan: <b>12345 1a2b3c4d5e...30a</b>", parse_mode="HTML", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "submit_homework"}


# Handler for back button during homework submission - must be registered before process_homework_answers
@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and 
                     m.chat.id in user_state and user_state[m.chat.id].get("step") == "submit_homework")
def back_from_submit_homework(message):
    user_state.pop(message.chat.id, None)
    # Navigate back to homework menu
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Uyga vazifa natijalari", "📝 Uyga vazifa topshirish")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "📝 Uyga vazifa bo'limi:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "homework_menu"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "submit_homework")
def process_homework_answers(message):
    # Skip if this is the back button (handled by separate handler above)
    if message.text == "⬅️ Orqaga":
        return
    
    # To'lov tekshirish (state-based handler uchun)
    if message.from_user.id not in ADMIN_IDS:
        from handlers.payment_handlers import check_subscription
        sub = check_subscription(str(message.from_user.id))
        if not sub["active"]:
            text = "❌ <b>To'lov qilmagansiz!</b>\n\nIltimos, hisobingizni to'ldiring.\n💰 Oylik to'lov: 15,000 so'm\n\nTo'lov qilish uchun pastdagi tugmani bosing."
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💳 Hisobni to'ldirish", callback_data="topup_account"))
            bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)
            user_state.pop(message.chat.id, None)
            return
    
    text = message.text.strip()
    
    parts = text.split(None, 1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Noto'g'ri format. Format: <b>ID 1a2a3a4b5c...30a</b>\nMasalan: <b>12345 1a2b3c4d5e...30a</b>", parse_mode="HTML")
        return
    
    homework_id = parts[0].strip()
    answers_text = parts[1].strip()
    
    test = query_db("SELECT test_name, correct_answers FROM tests WHERE test_id = ? AND is_homework = 1", (homework_id,), fetch=True)
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
    
    user_display = f"@{username}" if username else f"tg:{tg_id}"
    admin_caption = f"📥 Uyga vazifa topshirildi:\n🧑‍🎓 {student_name}\n🆔 {homework_id}\n✅ {correct} | ❌ {incorrect}\n{user_display}"
    
    for admin in ADMIN_IDS:
        try:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🚫 Bloklash", callback_data=f"quick_block:{message.from_user.id}"))
            bot.send_message(admin, admin_caption, reply_markup=kb)
        except Exception as e:
            logger.exception(f"Send to admin error: {e}")
    
    user_state.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "📊 Uyga vazifa natijalari" and m.from_user.id not in ADMIN_IDS)
def show_homework_results(message):
    if require_payment(message):
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
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📥 PDF ko'chirib olish", callback_data="download_student_hw_pdf"))
    kb.add(types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)

# ==================== ADMIN HANDLERS ====================

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

@bot.message_handler(func=lambda m: m.text == "📝 Uyga vazifa" and m.from_user.id in ADMIN_IDS)
def admin_add_homework_shortcut(message):
    admin_homework_menu(message)

@bot.message_handler(func=lambda m: m.text == "➕ Uyga vazifa qo'shish" and m.from_user.id in ADMIN_IDS)
def admin_add_homework_start(message):
    bot.send_message(message.chat.id, "📚 Uyga vazifa nomini kiriting:", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "get_homework_name"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_homework_name")
def get_homework_name(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        admin_homework_menu(message)
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
        admin_homework_menu(message)
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

@bot.message_handler(func=lambda m: m.text == "📊 Uyga vazifa natijalari" and m.from_user.id in ADMIN_IDS)
def admin_show_homework_results(message):
    try:
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
    except Exception as e:
        logger.exception(f"Error in admin_show_homework_results: {e}")
        bot.send_message(message.chat.id, f"❌ Xatolik yuz berdi: {str(e)}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "select_homework_for_results" and m.from_user.id in ADMIN_IDS)
def show_homework_results_details(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        admin_homework_menu(message)
        return
    
    # Check if message starts with 📊 (homework results button)
    if not message.text.startswith("📊"):
        bot.send_message(message.chat.id, "❌ Noto'g'ri tanlov.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
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
    
    kb = types.InlineKeyboardMarkup()
    try:
        from pdf_generator import create_homework_results_pdf
        pdf_bytes = create_homework_results_pdf(test_name, homework_id, results)
        if pdf_bytes:
            kb.add(types.InlineKeyboardButton("📥 PDF ko'chirib olish", callback_data=f"download_hw_pdf:{homework_id}"))
    except Exception:
        pass
    kb.add(types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu"))
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)
    user_state.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "🗑 Uyga vazifa o'chirish" and m.from_user.id in ADMIN_IDS)
def admin_delete_homework_start(message):
    try:
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
    except Exception as e:
        logger.exception(f"Error in admin_delete_homework_start: {e}")
        bot.send_message(message.chat.id, f"❌ Xatolik yuz berdi: {str(e)}", reply_markup=admin_main_menu())

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "delete_homework" and m.from_user.id in ADMIN_IDS)
def admin_delete_selected_homework(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        admin_homework_menu(message)
        return
    
    # Check if message starts with 🗑 (delete homework button)
    if not message.text.startswith("🗑"):
        bot.send_message(message.chat.id, "❌ Noto'g'ri tanlov.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
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

# ==================== CALLBACK HANDLERS ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith("download_hw_pdf:"))
def handle_download_hw_pdf(call):
    try:
        homework_id = call.data.split(":", 1)[1]
        
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
            return
        
        results = query_db(
            "SELECT student_name, username, tg_id, correct_count, incorrect_count, date FROM results WHERE test_id = ? ORDER BY date DESC",
            (homework_id,),
            fetch=True
        ) or []
        
        if not results:
            bot.answer_callback_query(call.id, "❌ Natijalar topilmadi!", show_alert=True)
            return
        
        test_info = query_db("SELECT test_name FROM tests WHERE test_id = ?", (homework_id,), fetch=True)
        test_name = test_info[0][0] if test_info else "Noma'lum"
        
        from pdf_generator import create_homework_results_pdf
        pdf_bytes = create_homework_results_pdf(test_name, homework_id, results)
        
        if not pdf_bytes:
            bot.answer_callback_query(call.id, "❌ PDF yaratishda xatolik yuz berdi!", show_alert=True)
            return
        
        pdf_filename = f"uyga_vazifa_{homework_id}.pdf"
        bot.send_document(
            call.from_user.id,
            pdf_bytes,
            visible_file_name=pdf_filename,
            caption=f"📊 {test_name} - PDF Natijalar"
        )
        
        bot.answer_callback_query(call.id, "✅ PDF yuborild!", show_alert=False)
    except Exception as e:
        logger.exception(f"PDF download error: {e}")
        bot.answer_callback_query(call.id, f"❌ Xatolik: {str(e)[:50]}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "download_student_hw_pdf")
def handle_download_student_hw_pdf(call):
    try:
        username = call.from_user.username or None
        tg_id = str(call.from_user.id)
        
        all_results = query_db(
            """SELECT r.test_id, r.correct_count, r.incorrect_count, r.date, t.test_name, t.is_homework
                FROM results r 
                LEFT JOIN tests t ON r.test_id = t.test_id 
                WHERE (r.username = ? OR r.tg_id = ?) 
                ORDER BY r.date DESC""",
            (username, tg_id),
            fetch=True
        ) or []
        
        homework_results = []
        for r in all_results:
            test_id = str(r[0])
            is_homework = r[5] if len(r) > 5 else None
            is_homework_test = (is_homework == 1) or (len(test_id) == 5 and test_id.isdigit())
            if is_homework_test:
                homework_results.append((r[4] or "Noma'lum", r[0], r[1], r[2], r[3]))
        
        if not homework_results:
            bot.answer_callback_query(call.id, "❌ Hali uyga vazifa natijalari yo'q!", show_alert=True)
            return
        
        student_name = load_profile(call.from_user.id) or f"Student_{call.from_user.id}"
        
        from pdf_generator import create_student_homework_results_pdf
        pdf_bytes = create_student_homework_results_pdf(student_name, homework_results)
        
        if not pdf_bytes:
            bot.answer_callback_query(call.id, "❌ PDF yaratishda xatolik yuz berdi!", show_alert=True)
            return
        
        pdf_filename = f"{student_name}_uyga_vazifa_natijalari.pdf"
        bot.send_document(
            call.from_user.id,
            pdf_bytes,
            visible_file_name=pdf_filename,
            caption=f"📊 {student_name} - Uyga vazifa natijalari"
        )
        
        bot.answer_callback_query(call.id, "✅ PDF yuborild!", show_alert=False)
    except Exception as e:
        logger.exception(f"Student PDF download error: {e}")
        bot.answer_callback_query(call.id, f"❌ Xatolik: {str(e)[:50]}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu_callback(call):
    from utils import admin_main_menu, user_main_menu
    
    if call.from_user.id in ADMIN_IDS:
        bot.send_message(call.from_user.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
    else:
        bot.send_message(call.from_user.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    
    bot.answer_callback_query(call.id)
