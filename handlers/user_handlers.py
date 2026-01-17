import re
import logging
from datetime import datetime
from telebot import types
from config import bot, ADMIN_IDS, user_state, user_profiles
from database import (
    query_db, load_profile, save_profile, get_name_changes, 
    increment_name_changes, get_balance
)
from utils import user_main_menu, back_button, extract_answers

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

@bot.message_handler(func=lambda m: m.text is not None and m.text.strip() == "⬅️ Orqaga" and 
                     (m.chat.id not in user_state or 
                      m.chat.id in user_state and user_state[m.chat.id].get("step") not in 
                      ["submit_homework", "get_homework_name", "get_homework_answers", 
                       "select_homework_for_results", "delete_homework", "get_test_answers",
                       "edit_name", "get_name", "quiz_menu", "quiz_wait_image", "homework_menu",
                       "homework_admin_menu"]))
def global_back_handler(message):
    # Ensure any pending state is cleared and immediately return to main menu
    user_state.pop(message.chat.id, None)
    return go_back(message)

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_name")
def get_name(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ Ism familiyangizni kiriting, bo'sh bo'lmaydi.")
        return
    user_state.setdefault(message.chat.id, {})["student_name"] = name
    user_profiles[message.chat.id] = name
    user_state[message.chat.id]["step"] = "main_menu"
    save_profile(message.chat.id, name, message.from_user.username or None)
    bot.send_message(message.chat.id, f"👋 Xush kelibsiz, {name}!", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.text == "✏️ Ismni tahrirlash")
def edit_name_start(message):
    if require_payment(message):
        return
    changes = get_name_changes(message.chat.id)
    if changes >= 3:
        bot.send_message(message.chat.id, "❌ Siz ismni faqat 3 marta o'zgartira olasiz.")
        return
    bot.send_message(message.chat.id, "✏️ Yangi ism familiyangizni kiriting:", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "edit_name"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "edit_name")
def save_new_name(message):
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
    
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)

    new_name = message.text.strip()
    if not new_name:
        bot.send_message(message.chat.id, "❌ Ism bo'sh bo'lishi mumkin emas.")
        return

    changes = get_name_changes(message.chat.id)
    if changes >= 3:
        bot.send_message(message.chat.id, "❌ Siz ismni faqat 3 marta o'zgartira olasiz.")
        user_state.pop(message.chat.id, None)
        return

    increment_name_changes(message.chat.id)
    save_profile(message.chat.id, new_name, message.from_user.username or None)
    user_profiles[message.chat.id] = new_name
    user_state.pop(message.chat.id, None)

    bot.send_message(
        message.chat.id,
        f"✅ Ismingiz yangilandi: {new_name}\n✏️ Siz {changes+1}/3 marta o'zgartirdingiz.",
        reply_markup=user_main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💰 Balans" and m.from_user.id not in ADMIN_IDS)
def show_balance(message):
    if require_payment(message):
        return
    bal = get_balance(message.chat.id)
    bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {bal} som", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.text == "📝 Test topshirish")
def submit_test_start(message):
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
    
    saved_name = load_profile(message.chat.id) or user_state.get(message.chat.id, {}).get("student_name")
    user_state[message.chat.id] = {"step": "get_test_answers", "student_name": saved_name}
    bot.send_message(message.chat.id, "Test ID va javoblaringizni yuboring:\nMasalan: <b>B4086 1a2b3c...</b>", reply_markup=back_button(), parse_mode="HTML")


# Handler for back button during test submission - must be registered before process_test_answers
@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and 
                     m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_test_answers")
def back_from_submit_test(message):
    user_state.pop(message.chat.id, None)
    return go_back(message)

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "get_test_answers")
def process_test_answers(message):
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

    state = user_state.get(message.chat.id, {})
    student_name = state.get("student_name") or load_profile(message.chat.id) or "Unknown"
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)

    text = (message.text or "").strip()
    parts = text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Noto'g'ri format. Masalan:\n<b>B4086 1a2b3c...</b>", parse_mode="HTML")
        return
    test_id, user_answers = parts[0], ''.join(parts[1:])
    test = query_db("SELECT correct_answers FROM tests WHERE test_id = ?", (test_id,), fetch=True)
    if not test:
        bot.send_message(message.chat.id, "❌ Bunday test topilmadi.")
        return

    correct_list = extract_answers(test[0][0])
    user_list = extract_answers(user_answers)
    if not user_list:
        bot.send_message(message.chat.id, "❌ Javoblarda A-E orasidagi harflar bo'lishi shart.")
        return

    total_questions = len(correct_list)
    correct = 0
    incorrect_details = []
    for i in range(total_questions):
        ua = user_list[i] if i < len(user_list) else None
        ca = correct_list[i]
        if ua is not None and ua == ca:
            correct += 1
        else:
            incorrect_details.append((i + 1, ua))

    incorrect = total_questions - correct

    query_db(
        "INSERT INTO results (student_name, username, tg_id, test_id, correct_count, incorrect_count, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (student_name, username, tg_id, test_id, correct, incorrect, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    user_display = f"@{username}" if username else f"tg:{tg_id}"

    result_count = query_db(
        "SELECT COUNT(*) FROM results WHERE (username = ? OR tg_id = ?) AND test_id = ?",
        (username, tg_id, test_id),
        fetch=True
    )
    attempt_number = result_count[0][0] if result_count else 1

    result_text = f"📊 Natijangiz:\n🧑‍🎓 {student_name} ({user_display})\n"
    result_text += f"🆔 {test_id}\n✅ {correct}\n❌ {incorrect}\n"
    
    if incorrect_details:
        result_text += "\n❗ Xato javoblar:\n"
        for qnum, ua in incorrect_details:
            ua_display = ua.upper() if ua else "—"
            result_text += f"{qnum}-savol: Siz belgilagan javob <b>{ua_display}</b> ❌\n"

    bot.send_message(message.chat.id, result_text, reply_markup=user_main_menu(), parse_mode="HTML")

    admin_caption = f"📥 Test topshirildi ({attempt_number}-natijasi):\n🧑‍🎓 {student_name}\n🆔 {test_id}\n✅ {correct} | ❌ {incorrect}\n{('@' + username) if username else 'tg:' + tg_id}"

    for admin in ADMIN_IDS:
        try:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🚫 Bloklash", callback_data=f"quick_block:{message.from_user.id}"))
            bot.send_message(admin, admin_caption, reply_markup=kb)
        except Exception as e:
            logger.exception(f"Send to admin error: {e}")

    user_state.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "📈 Mening natijalarim")
def show_my_results(message):
    if require_payment(message):
        return
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)
    
    if username:
        all_results = query_db(
            """SELECT r.test_id, r.correct_count, r.incorrect_count, r.date, t.test_name, t.is_homework
                FROM results r 
                LEFT JOIN tests t ON r.test_id = t.test_id 
                WHERE (r.username = ? OR r.tg_id = ?) 
                ORDER BY r.test_id ASC, r.date ASC""", 
            (username, tg_id), 
            fetch=True
        ) or []
    else:
        all_results = query_db(
            """SELECT r.test_id, r.correct_count, r.incorrect_count, r.date, t.test_name, t.is_homework
                FROM results r 
                LEFT JOIN tests t ON r.test_id = t.test_id 
                WHERE r.tg_id = ? 
                ORDER BY r.test_id ASC, r.date ASC""", 
            (tg_id,), 
            fetch=True
        ) or []
    
    results = []
    for r in all_results:
        test_id = str(r[0])
        is_homework = r[5] if len(r) > 5 else None
        is_homework_test = (is_homework == 1) or (len(test_id) == 5 and test_id.isdigit())
        if not is_homework_test:
            results.append((r[0], r[1], r[2], r[3], r[4]))
    
    if not results:
        bot.send_message(message.chat.id, "📭 Siz hali testlarni topshirmadingiz.", reply_markup=user_main_menu())
        return
    
    text = "📊 <b>Sizning natijalaringiz:</b>\n\n"
    
    grouped_results = {}
    for r in results:
        test_id = r[0]
        correct = r[1]
        incorrect = r[2]
        date = r[3]
        test_name = r[4] if len(r) > 4 and r[4] else "Noma'lum test"
        
        if test_id not in grouped_results:
            grouped_results[test_id] = {"name": test_name, "attempts": []}
        grouped_results[test_id]["attempts"].append((correct, incorrect, date))
    
    for test_id, data in grouped_results.items():
        test_name = data["name"]
        attempts = data["attempts"]
        
        text += f"<b>🆔 {test_id}</b> - {test_name}\n"
        for attempt_num, (correct, incorrect, date) in enumerate(attempts, 1):
            total = correct + incorrect
            percentage = (correct / total * 100) if total > 0 else 0
            text += f"  {attempt_num}-natijangiz: ✅ {correct} | ❌ {incorrect} | 📊 {percentage:.1f}% | 🕓 {date}\n"
        text += "\n"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=user_main_menu())

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "view_test_answers")
def show_test_correct_answers(message):
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
    
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        return go_back(message)
    
    if "📋" in message.text and "- javoblar" in message.text:
        test_id = message.text.replace("📋", "").replace("- javoblar", "").strip()
    else:
        test_id = message.text.strip()
    
    test = query_db("SELECT test_name, correct_answers, is_homework FROM tests WHERE test_id = ?", (test_id,), fetch=True)
    if not test:
        bot.send_message(message.chat.id, "❌ Bunday test topilmadi.", reply_markup=user_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    test_id_str = str(test_id)
    is_homework = test[0][2] if len(test[0]) > 2 else None
    is_homework_test = (is_homework == 1) or (len(test_id_str) == 5 and test_id_str.isdigit())
    
    if is_homework_test:
        bot.send_message(message.chat.id, "❌ Bu uyga vazifa. Uyga vazifa javoblarini ko'rish mumkin emas.", reply_markup=user_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    test_name = test[0][0]
    correct_answers = test[0][1]
    
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)
    user_results = query_db(
        "SELECT correct_count, incorrect_count, date FROM results WHERE (username = ? OR tg_id = ?) AND test_id = ? ORDER BY date DESC LIMIT 1",
        (username, tg_id, test_id),
        fetch=True
    )
    
    if not user_results:
        bot.send_message(message.chat.id, "❌ Siz bu testni ishlamagansiz.", reply_markup=user_main_menu())
        user_state.pop(message.chat.id, None)
        return
    
    correct_count, incorrect_count, date = user_results[0]
    
    text = f"📊 <b>Test javoblari</b>\n\n"
    text += f"🆔 Test ID: {test_id}\n"
    text += f"📘 Nomi: {test_name}\n"
    text += f"📅 Topshirilgan: {date}\n"
    text += f"✅ To'g'ri: {correct_count} | ❌ Xato: {incorrect_count}\n\n"
    text += f"<b>📝 To'g'ri javoblar:</b>\n\n"
    
    answers_list = list(correct_answers)
    for i, answer in enumerate(answers_list, 1):
        text += f"{i}. {answer.upper()}\n"
        if i % 10 == 0:
            text += "\n"
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📈 Mening natijalarim")
    kb.add("⬅️ Orqaga")
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🎬 Videolar")
def show_user_videos(message):
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
    
    username = message.from_user.username or None
    tg_id = str(message.from_user.id)
    videos = query_db("SELECT v.test_id, t.test_name, v.video_url FROM videos v LEFT JOIN tests t ON v.test_id = t.test_id ORDER BY v.created_at ASC", fetch=True)
    
    if not videos:
        bot.send_message(message.chat.id, "📭 Hozircha hech qanday video qo'shilmagan.", reply_markup=user_main_menu())
        return
    
    kb = types.InlineKeyboardMarkup()
    any_button = False
    for idx, v in enumerate(videos, 1):
        test_id, test_name, video_url = v
        if video_url:
            test_name = test_name or "Noma'lum test"
            kb.add(types.InlineKeyboardButton(text=f"{idx}-{test_name} ({test_id})", url=video_url))
            any_button = True
    
    if not any_button:
        bot.send_message(message.chat.id, "📭 Hozircha hech qanday video qo'shilmagan.", reply_markup=user_main_menu())
        return
    
    bot.send_message(message.chat.id, "🎬 Quyidagi tugmalardan videoni oching:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🧑🏻‍💻About founder")
def about_founder(message):
    if require_payment(message):
        return
    kb = types.InlineKeyboardMarkup()
    

    kb.add(types.InlineKeyboardButton(text="Telegram", callback_data="founder_tg"))
    kb.add(types.InlineKeyboardButton(text="Instagram", callback_data="founder_insta"))
    kb.add(types.InlineKeyboardButton(text="GitHub", callback_data="founder_github"))
    kb.add(types.InlineKeyboardButton(text="Facebook", callback_data="founder_fb"))
    kb.add(types.InlineKeyboardButton(text="Gmail", callback_data="founder_mail"))
    kb.add(types.InlineKeyboardButton(text="Telefon", callback_data="founder_phone"))

    text = (
        "👨‍💻 <b>Founder haqida</b>\n\n"
        "Quyidagi tugmalar orqali menga yozishingiz yoki qo'ng'iroq qilishingiz mumkin:"
    )
    bot.send_message(message.chat.id, text, reply_markup=kb)
@bot.callback_query_handler(func=lambda c: c.data == "founder_phone")
def founder_phone_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    phone = "+998942686663"
    try:
        # Try to send contact
        bot.send_contact(call.message.chat.id, phone_number=phone, first_name="Sherbek", last_name="Kubayev")
    except Exception as e:
        # Fallback: send phone number as text
        bot.send_message(call.message.chat.id, f"📞 Telefon raqam: {phone}")

@bot.callback_query_handler(func=lambda c: c.data == "founder_mail")
def founder_mail_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    
    email = "kubayevsherbek@gmail.com"
    # Send email as text (mailto links don't work in inline buttons)
    bot.send_message(call.message.chat.id, f"📧 Email: {email}\n\nEmail yozish uchun: mailto:{email}")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("founder_") and c.data not in ["founder_phone", "founder_mail"])
def founder_link_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    links = {
        "founder_tg": "https://t.me/sherbekkubayev",
        "founder_insta": "https://www.instagram.com/sherbekkubayev/",
        "founder_github": "https://github.com/kubayevvv7",
        "founder_fb": "https://www.facebook.com/sherbekkubayev",
    }

    url = links.get(call.data)
    if url:
        # Send URL as text so user can click it
        bot.send_message(call.message.chat.id, f"🔗 {url}")

@bot.message_handler(func=lambda m: m.text == "💳 To'lov")
def show_payment_menu(message):
    """To'lov menyusi"""
    from handlers.payment_handlers import show_payment_menu
    show_payment_menu(message)

def go_back(message):
    # Return user to appropriate main menu and clear any state
    try:
        if message.from_user.id in ADMIN_IDS:
            from utils import admin_main_menu
            bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
        else:
            bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    except Exception:
        # Fallback: send a simple text message
        try:
            bot.send_message(message.chat.id, "🏠 Bosh menyu")
        except Exception:
            pass
    user_state.pop(message.chat.id, None)
