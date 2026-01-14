import os
import re
import time
import logging
from datetime import datetime
from telebot import types
from config import bot, ADMIN_IDS, user_state, VIDEOS_FOLDER, logger
from database import (
    query_db, get_all_active_quizzes, get_unsent_quiz, mark_quiz_as_sent,
    get_quiz_hours_remaining, create_quiz, update_user_balance
)
from utils import admin_main_menu, back_button

@bot.message_handler(func=lambda m: m.text == "🧩 Viktorina savollari")
def admin_quiz_menu(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Viktorina savolini qo'shish", "🗑️ Viktorina savolini o'chirish")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "Viktorina boshqaruvi: tanlang", reply_markup=kb)
    user_state[message.chat.id] = {"step": "quiz_menu"}

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and m.chat.id in user_state and user_state[m.chat.id].get("step") == "quiz_menu")
def back_from_quiz_menu(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    user_state.pop(message.chat.id, None)
    from handlers.admin_handlers import go_back
    go_back(message)

@bot.message_handler(func=lambda m: m.text == "➕ Viktorina savolini qo'shish")
def admin_quiz_add_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "📸 Iltimos viktorina savoli uchun rasm yuboring.", reply_markup=back_button())
    user_state[message.chat.id] = {"step": "quiz_wait_image"}

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and m.chat.id in user_state and user_state[m.chat.id].get("step") == "quiz_wait_image")
def back_from_quiz_image(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    user_state.pop(message.chat.id, None)
    admin_quiz_menu(message)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    state = user_state.get(message.chat.id, {})
    if state and state.get("step") == "quiz_wait_image" and message.from_user.id in ADMIN_IDS:
        photo = message.photo[-1]
        file_id = photo.file_id
        try:
            file_info = bot.get_file(file_id)
            downloaded = bot.download_file(file_info.file_path)
            fname = f"quiz_{int(time.time())}_{file_id}.jpg"
            path = os.path.join(VIDEOS_FOLDER, fname)
            with open(path, 'wb') as f:
                f.write(downloaded)
        except Exception:
            logger.exception("Failed to download quiz image")
            bot.send_message(message.chat.id, "❌ Rasmni yuklashda xatolik sodir bo'ldi.", reply_markup=admin_main_menu())
            user_state.pop(message.chat.id, None)
            return

        user_state[message.chat.id] = {"step": "quiz_wait_correct", "file_path": path, "file_id": file_id}
        kb = types.InlineKeyboardMarkup()
        row = []
        for opt in ["A", "B", "C", "D", "E"]:
            row.append(types.InlineKeyboardButton(text=opt, callback_data=f"set_quiz_correct:{opt}"))
        kb.row(*row)
        bot.send_message(message.chat.id, "🔘 Endi to'g'ri javobni tanlang:", reply_markup=kb)
        return

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_quiz_correct:"))
def handle_set_quiz_correct(call):
    try:
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Ruxsat yo'q")
            return
        opt = call.data.split(":", 1)[1]
        state = user_state.get(call.from_user.id, {})
        if not state or state.get("step") != "quiz_wait_correct":
            bot.answer_callback_query(call.id, "Ichki xatolik yoki vaqt tugadi.")
            return
        file_path = state.get("file_path")
        file_id = state.get("file_id")
        if not file_path or not os.path.exists(file_path):
            bot.answer_callback_query(call.id, "Rasm topilmadi.")
            user_state.pop(call.from_user.id, None)
            return
        create_quiz(file_path, file_id, opt)
        user_state.pop(call.from_user.id, None)
        bot.answer_callback_query(call.id, "✅ Javob saqlandi")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, f"✅ Viktorina savoli saqlandi. To'g'ri javob: {opt}", reply_markup=admin_main_menu())
    except Exception:
        logger.exception("Error in handle_set_quiz_correct")
        try:
            bot.answer_callback_query(call.id, "Xatolik")
        except Exception:
            pass

@bot.message_handler(func=lambda m: m.text == "🗑️ Viktorina savolini o'chirish")
def admin_quiz_delete_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    quizzes = get_all_active_quizzes()
    if not quizzes:
        bot.send_message(message.chat.id, "📭 Hozircha aktiv viktorina savollari mavjud emas.", reply_markup=admin_main_menu())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for q in quizzes:
        qid, file_path, file_id, correct, created_at, sent_at, hours_remaining, sent_to_users = q
        short = os.path.basename(file_path) if file_path else f"quiz_{qid}"
        kb.add(f"❌ {qid} — {short} ({correct})")
    kb.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "O'chirish uchun savolni tanlang:", reply_markup=kb)
    user_state[message.chat.id] = {"step": "delete_quiz"}

@bot.message_handler(func=lambda m: m.chat.id in user_state and user_state[m.chat.id].get("step") == "delete_quiz")
def admin_delete_selected_quiz(message):
    if message.text == "⬅️ Orqaga":
        user_state.pop(message.chat.id, None)
        admin_quiz_menu(message)
        return
    if message.from_user.id not in ADMIN_IDS:
        return
    match = re.search(r"(\d+)", message.text)
    if not match:
        bot.send_message(message.chat.id, "❌ Noto'g'ri tanlov. Iltimos menyudan tanlang.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    qid = int(match.group(1))
    r = query_db("SELECT file_path FROM quizzes WHERE id = ? AND active = 1", (qid,), fetch=True)
    if not r:
        bot.send_message(message.chat.id, "❌ Bunday aktiv savol topilmadi.", reply_markup=admin_main_menu())
        user_state.pop(message.chat.id, None)
        return
    file_path = r[0][0]
    query_db("UPDATE quizzes SET active = 0 WHERE id = ?", (qid,))
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
    bot.send_message(message.chat.id, f"✅ Savol o'chirildi (id: {qid})", reply_markup=admin_main_menu())
    user_state.pop(message.chat.id, None)

def send_quiz_to_users(quiz_id, file_id, correct_answer):
    """Barcha userlarga viktorina savolini yuboradi"""
    if ADMIN_IDS:
        placeholders = ','.join(['?' for _ in ADMIN_IDS])
        users = query_db(f"SELECT chat_id FROM users WHERE chat_id NOT IN ({placeholders})", [str(aid) for aid in ADMIN_IDS], fetch=True) or []
    else:
        users = query_db("SELECT chat_id FROM users", fetch=True) or []
    
    if not users:
        logger.info("Viktorina yuborish uchun userlar topilmadi")
        return 0
    
    if not file_id:
        logger.error(f"Viktorina {quiz_id} uchun file_id topilmadi")
        return 0
    
    kb = types.InlineKeyboardMarkup()
    row = []
    for opt in ["A", "B", "C", "D", "E"]:
        row.append(types.InlineKeyboardButton(text=opt, callback_data=f"quiz_answer:{quiz_id}:{opt}"))
    kb.row(*row)
    
    sent_count = 0
    failed_count = 0
    for (chat_id,) in users:
        try:
            try:
                chat_id_int = int(chat_id)
            except (ValueError, TypeError):
                logger.warning(f"Noto'g'ri chat_id: {chat_id}")
                failed_count += 1
                continue
            
            bot.send_photo(chat_id_int, file_id, caption="🧩 <b>Viktorina savoli</b>\n⏰ Qolgan vaqt: 24 soat", parse_mode="HTML", reply_markup=kb)
            sent_count += 1
            if sent_count % 10 == 0:
                time.sleep(0.1)
        except Exception as e:
            logger.warning(f"User {chat_id} ga viktorina yuborishda xatolik: {e}")
            failed_count += 1
    
    logger.info(f"Viktorina savoli {sent_count} ta userga yuborildi, {failed_count} ta xatolik")
    return sent_count

def quiz_dispatcher_loop():
    """Har 2 soatda viktorina savolini yuboradi (bir kunda 12 ta)"""
    logger.info("🧩 Viktorina dispatcher loop ishga tushdi")
    first_run = True
    
    while True:
        try:
            if first_run:
                logger.info("🔍 Viktorina savollarini tekshiryapman...")
                first_run = False
            
            quiz = get_unsent_quiz()
            if quiz:
                quiz_id, file_id, correct_answer, sent_to_users = quiz
                logger.info(f"📤 Viktorina savoli yuborilmoqda: ID {quiz_id}")
                sent_count = send_quiz_to_users(quiz_id, file_id, correct_answer)
                mark_quiz_as_sent(quiz_id)
                logger.info(f"✅ Viktorina savoli {sent_count} ta userga yuborildi")
            else:
                logger.info("📭 Yuborish uchun viktorina savoli topilmadi")
            
            logger.info("⏰ Keyingi tekshirish 2 soatdan keyin...")
            time.sleep(7200)  # 2 soat = 7200 soniya
        except Exception as e:
            logger.exception(f"❌ Viktorina dispatcher xatosi: {e}")
            logger.info("🔄 1 minutdan keyin qayta uriniladi...")
            time.sleep(60)

@bot.callback_query_handler(func=lambda call: call.data.startswith("quiz_answer:"))
def handle_quiz_answer(call):
    try:
        if call.from_user.id in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Adminlar javob bera olmaydi")
            return
        
        parts = call.data.split(":")
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "Xatolik")
            return
        
        quiz_id = int(parts[1])
        user_answer = parts[2]
        
        quiz_info = query_db("SELECT correct_answer, sent_at, hours_remaining FROM quizzes WHERE id = ? AND active = 1", (quiz_id,), fetch=True)
        if not quiz_info:
            bot.answer_callback_query(call.id, "Savol topilmadi yoki aktiv emas")
            return
        
        correct_answer, sent_at, hours_remaining = quiz_info[0]
        remaining = get_quiz_hours_remaining(quiz_id)
        
        if remaining is None or remaining <= 0:
            bot.answer_callback_query(call.id, "⏰ Vaqt tugadi!")
            try:
                # Avval tugmalarni o'chiramiz
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                # Keyin captionni yangilaymiz
                bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption="⏰ <b>Vaqt tugadi!</b>", parse_mode="HTML", reply_markup=None)
            except Exception:
                pass
            return
        
        chat_id = call.message.chat.id
        user_quiz_key = f"quiz_{quiz_id}_{call.from_user.id}"
        if user_quiz_key in user_state.get(chat_id, {}).get("answered_quizzes", []):
            bot.answer_callback_query(call.id, "Siz allaqachon javob berdingiz!")
            return
        
        is_correct = user_answer.upper() == correct_answer.upper()
        
        if is_correct:
            new_balance = update_user_balance(call.from_user.id, 100)
            result_text = f"✅ <b>To'g'ri javob!</b>\n💰 Sizga 100 som qo'shildi\n💰 Joriy balans: {new_balance} som"
        else:
            result_text = f"❌ <b>Noto'g'ri javob</b>\nTo'g'ri javob: <b>{correct_answer}</b>"
        
        if chat_id not in user_state:
            user_state[chat_id] = {}
        if "answered_quizzes" not in user_state[chat_id]:
            user_state[chat_id]["answered_quizzes"] = []
        user_state[chat_id]["answered_quizzes"].append(user_quiz_key)
        
        bot.answer_callback_query(call.id, "✅ Javob qabul qilindi")
        try:
            # Avval tugmalarni o'chiramiz
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            # Keyin captionni yangilaymiz
            bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=result_text, parse_mode="HTML", reply_markup=None)
        except Exception as e:
            # Agar edit ishlamasa, yangi xabar yuboramiz
            try:
                bot.send_message(call.message.chat.id, result_text, parse_mode="HTML")
            except Exception:
                pass
    except Exception:
        logger.exception("Error in handle_quiz_answer")
        try:
            bot.answer_callback_query(call.id, "Xatolik")
        except Exception:
            pass





