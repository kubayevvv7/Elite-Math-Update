import logging
from datetime import datetime, timedelta
from telebot import types
from config import bot, ADMIN_IDS, user_state
from database import query_db

logger = logging.getLogger(__name__)

WAITING_CONFIRMATION = "waiting_confirmation"

def get_active_card():
    """Faol karta raqamini olish (eski funksiya - orqaga moslik uchun)"""
    result = query_db(
        "SELECT card_number, card_owner, bank_name FROM bot_cards WHERE is_active = 1 LIMIT 1",
        fetch=True
    )
    return result[0] if result else None

def get_active_cards():
    """Barcha faol kartalarni olish"""
    result = query_db(
        "SELECT id, card_number, card_owner, bank_name FROM bot_cards WHERE is_active = 1 ORDER BY id ASC",
        fetch=True
    )
    return result if result else []

def get_card_for_user(user_id):
    """User ID ga qarab toq/juft aniqlash va tegishli kartani qaytarish"""
    active_cards = get_active_cards()
    
    if not active_cards:
        return None
    
    if len(active_cards) == 1:
        # Agar faqat bitta karta bo'lsa, uni qaytarish
        card = active_cards[0]
        return {
            "id": card[0],
            "visible_id": 1,  # Ko'rinadigan ID
            "card_number": card[1],
            "card_owner": card[2],
            "bank_name": card[3]
        }
    
    # User ID ni son sifatida olish
    try:
        user_id_int = int(user_id)
        # Toq yoki juft aniqlash
        is_odd = user_id_int % 2 == 1
        
        if is_odd:
            # Toq userlar uchun birinchi karta
            card = active_cards[0]
            visible_id = 1
        else:
            # Juft userlar uchun ikkinchi karta
            card = active_cards[1] if len(active_cards) > 1 else active_cards[0]
            visible_id = 2 if len(active_cards) > 1 else 1
        
        return {
            "id": card[0],
            "visible_id": visible_id,  # Ko'rinadigan ID
            "card_number": card[1],
            "card_owner": card[2],
            "bank_name": card[3]
        }
    except (ValueError, TypeError):
        # Agar user_id son bo'lmasa, birinchi kartani qaytarish
        card = active_cards[0]
        return {
            "id": card[0],
            "visible_id": 1,  # Ko'rinadigan ID
            "card_number": card[1],
            "card_owner": card[2],
            "bank_name": card[3]
        }

def check_subscription(user_id):
    """Foydalanuvchining obunasini tekshirish"""
    result = query_db(
        "SELECT id, is_active, end_date FROM subscriptions WHERE user_id = ? AND is_active = 1",
        (str(user_id),),
        fetch=True
    )
    
    if result:
        sub_id, is_active, end_date = result[0]
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            if end_dt > datetime.now():
                return {"active": True, "end_date": end_date}
            else:
                # Obunani deaktiv qilish
                query_db("UPDATE subscriptions SET is_active = 0 WHERE id = ?", (sub_id,))
        except:
            pass
    
    return {"active": False, "end_date": None}

@bot.message_handler(func=lambda m: m.text == "💳 To'lov")
def show_payment_menu(message):
    """To'lov menyusi"""
    user_id = str(message.from_user.id)
    
    # Obunani tekshirish
    sub = check_subscription(user_id)
    
    if sub["active"]:
        end_date = sub["end_date"]
        text = f"✅ <b>Siz faol obunachisiz!</b>\n\n"
        text += f"📅 Tugash sanasi: {end_date}\n"
        text += f"💰 Oylik to'lov: 15,000 so'm\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔄 Obunani yangilash", callback_data="renew_subscription"))
        kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_menu"))
        
        # Faol obunachi bo'lsa, bosh menyuni qaytarish
        from utils import user_main_menu
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=user_main_menu())
        bot.send_message(message.chat.id, "Yoki pastdagi tugmalardan birini tanlang:", reply_markup=kb)
    else:
        text = f"❌ <b>Siz obunachimiz emassiz</b>\n\n"
        text += f"💰 Oylik to'lov narxi: <b>15,000 so'm</b>\n"
        text += f"⏱️ Muddati: 1 oy\n\n"
        text += f"<i>Hisobni to'ldirish uchun pastdagi tugmani bosing</i>"
        
        # Faqat to'lov tugmasi bilan keyboard
        payment_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        payment_kb.add("💳 To'lov")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Hisobni to'ldirish", callback_data="topup_account"))
        
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=payment_kb)
        bot.send_message(message.chat.id, "Yoki pastdagi tugmani bosing:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "topup_account")
def topup_account_callback(call):
    """Hisobni to'ldirish - KARTA RAQAMI YUBORISH"""
    bot.answer_callback_query(call.id)
    
    user_id = str(call.from_user.id)
    username = call.from_user.username or "noma'lum"
    full_name = call.from_user.full_name or "noma'lum"
    
    # Mavjud to'lovni tekshirish
    pending = query_db(
        "SELECT id, card_number FROM payments WHERE user_id = ? AND status = 'pending'",
        (user_id,),
        fetch=True
    )
    
    if pending:
        payment_id, card_number = pending[0]
        
        # Karta raqamining oxirgi 4 raqamini olish
        card_digits = card_number.replace(" ", "").replace("-", "")
        last_four = card_digits[-4:] if len(card_digits) >= 4 else ""
        
        # Karta raqamiga qarab admin username'ini aniqlash
        admin_username = None
        if last_four == "6035":
            admin_username = "@sherbekkubayev"
        elif last_four == "9657":
            admin_username = "@math_3322"
        
        text = "⏳ <b>Siz allaqachon to'lovni kutmoqdasiz!</b>\n\n"
        text += "Admin to'lovni tekshirgungacha kuting.\n"
        if admin_username:
            text += f"Agar ko'p vaqt kutgan bo'lsangiz, murojaat qiling: {admin_username}"
        else:
            text += "Agar ko'p vaqt kutgan bo'lsangiz, admin bilan bog'laning."
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="payment_menu"))
        
        bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=kb)
        return
    
    # User ID ga qarab toq/juft aniqlash va tegishli kartani olish
    card_data = get_card_for_user(user_id)
    
    if not card_data:
        text = "❌ <b>Xato bo'ldi!</b>\n\n"
        text += "Karta raqami topilmadi. Admin bilan bog'laning."
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="payment_menu"))
        
        bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=kb)
        return
    
    card_number = card_data["card_number"]
    card_owner = card_data["card_owner"]
    bank_name = card_data["bank_name"]
    visible_id = card_data.get("visible_id", 1)  # Ko'rinadigan ID
    
    user_state[call.from_user.id] = {
        "payment_user_id": user_id,
        "payment_username": username,
        "payment_full_name": full_name,
        "payment_card": card_number,
        "step": "waiting_payment_confirmation"
    }
    
    # Karta raqamini ko'rsatish
    text = "💳 <b>Bu karta raqamiga pul tashang</b>\n\n"
    text += f"🆔 <b>Karta ID:</b> {visible_id}\n"
    text += f"🏦 <b>Bank:</b> {bank_name}\n"
    text += f"👤 <b>Egasi:</b> {card_owner}\n"
    text += f"💳 <b>Karta raqami:</b> <code>{card_number}</code>\n"
    text += f"💰 <b>Summa:</b> 15,000 so'm\n\n"
    text += f"<i>Karta raqamini ko'chib olish uchun ustiga bosing</i>\n\n"
    text += f"<b>Pul tashagandan keyin pastdagi tugmani bosing</b>"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Pul tashadim", callback_data="confirm_payment_sent"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_payment"))
    
    bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_payment_sent")
def confirm_payment_sent_callback(call):
    """Pul tashtim tugmasi bosildi"""
    bot.answer_callback_query(call.id)
    
    state = user_state.get(call.from_user.id, {})
    user_id = state.get("payment_user_id")
    username = state.get("payment_username")
    full_name = state.get("payment_full_name")
    card_number = state.get("payment_card")
    
    if not user_id:
        bot.send_message(call.from_user.id, "❌ Xato bo'ldi. Qayta urinib ko'ring.")
        return
    
    # Database ga to'lov recordi yaratish
    query_db(
        "INSERT INTO payments (user_id, username, student_name, card_number, status, payment_date) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, full_name, card_number, "pending", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    
    # Payment ID ni olish
    payment = query_db(
        "SELECT id FROM payments WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
        (user_id,),
        fetch=True
    )
    payment_id = payment[0][0] if payment else None
    
    user_state[call.from_user.id]["payment_id"] = payment_id
    
    # User xabari
    text = "⏳ <b>To'lov tekshirilmoqda...</b>\n\n"
    text += f"💳 Karta: {card_number}\n"
    text += f"💰 Summa: 15,000 so'm\n\n"
    text += "Admin to'lovni tekshiradi. Kuting..."
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="payment_menu"))
    
    bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=kb)
    
    # Admin ga bildirishnoma
    text_admin = f"🔔 <b>Yangi to'lov tekshirilishi kerak!</b>\n\n"
    text_admin += f"👤 Foydalanuvchi: @{username}\n"
    text_admin += f"📱 Ismi: {full_name}\n"
    text_admin += f"💳 Shu karta raqamiga pul tashadi: <code>{card_number}</code>\n"
    text_admin += f"💰 Summa: 15,000 so'm\n"
    text_admin += f"⏰ Vaqti: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    text_admin += f"<i>To'lov ID: {payment_id}</i>"
    
    kb_admin = types.InlineKeyboardMarkup()
    kb_admin.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"verify_payment_{payment_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment_id}")
    )
    
    # Karta raqamining oxirgi 4 raqamini olish (bo'shliqlarni olib tashlab)
    card_digits = card_number.replace(" ", "").replace("-", "")
    last_four = card_digits[-4:] if len(card_digits) >= 4 else ""
    
    # Karta raqamiga qarab maxsus adminlarga xabar yuborish
    specific_admin_id = None
    if last_four == "2717":
        specific_admin_id = 8527215472
    elif last_four == "9657":
        specific_admin_id = 1229135388
    
    # Faqat karta raqamiga qarab tegishli adminga xabar yuborish
    if specific_admin_id:
        try:
            bot.send_message(specific_admin_id, text_admin, parse_mode="HTML", reply_markup=kb_admin)
        except Exception as e:
            logger.exception(f"Send to specific admin {specific_admin_id} error: {e}")
    else:
        # Agar karta raqami 2717 yoki 9657 bilan tugamasa, barcha adminlarga yuborish
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, text_admin, parse_mode="HTML", reply_markup=kb_admin)
            except Exception as e:
                logger.exception(f"Send to admin error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_payment_"))
def reject_payment_callback(call):
    """To'lovni rad etish"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    payment_id = int(call.data.split("_")[2])
    
    payment = query_db(
        "SELECT user_id, student_name, card_number FROM payments WHERE id = ?",
        (payment_id,),
        fetch=True
    )
    
    if not payment:
        bot.send_message(call.from_user.id, "❌ To'lov topilmadi")
        return
    
    user_id, student_name, card_number = payment[0]
    
    query_db("UPDATE payments SET status = 'rejected' WHERE id = ?", (payment_id,))
    
    # Admin xabari
    text = f"❌ <b>To'lov rad etildi</b>\n\n"
    text += f"Foydalanuvchi: {student_name}\n"
    text += f"Karta: {card_number}\n"
    text += f"To'lov ID: {payment_id}"
    
    bot.send_message(call.from_user.id, text, parse_mode="HTML")
    
    # Foydalanuvchiga xabar - hech qanday tugma bo'lmasin
    try:
        text_user = "❌ <b>To'lovingiz rad etildi!</b>\n\n"
        text_user += "Sababi:\n"
        text_user += "• Pul tasdiqlanmadi\n"
        text_user += "• Summa to'g'ri emas\n"
        text_user += "• Boshqa sabab\n\n"
        text_user += "Admin bilan bog'laning yoki qayta urinib ko'ring."
        
        # Hech qanday tugma bo'lmasin - faqat matn
        bot.send_message(int(user_id), text_user, parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
        
        # User state'ni tozalash
        if int(user_id) in user_state:
            user_state.pop(int(user_id), None)
    except Exception as e:
        logger.exception(f"User ga xabar yuborishda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_payment_"))
def verify_payment_callback(call):
    """To'lovni tasdiqlash"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    payment_id = int(call.data.split("_")[2])
    
    payment = query_db(
        "SELECT user_id, student_name, username, card_number FROM payments WHERE id = ?",
        (payment_id,),
        fetch=True
    )
    
    if not payment:
        bot.send_message(call.from_user.id, "❌ To'lov topilmadi")
        return
    
    user_id, student_name, username, card_number = payment[0]
    
    # To'lovni tasdiqlash
    query_db(
        "UPDATE payments SET status = 'verified', verified_date = ?, verified_by = ? WHERE id = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(call.from_user.id), payment_id)
    )
    
    # Obunani yaratish
    end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    
    query_db(
        "INSERT OR REPLACE INTO subscriptions (user_id, username, student_name, subscription_type, price, start_date, end_date, is_active, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, student_name, "monthly", 15000, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end_date, 1, payment_id)
    )
    
    # Admin xabari
    text = f"✅ <b>To'lov tasdiqlandi!</b>\n\n"
    text += f"Foydalanuvchi: {student_name}\n"
    text += f"Karta: {card_number}\n"
    text += f"Tugash sanasi: {end_date[:10]}\n"
    text += f"To'lov ID: {payment_id}"
    
    bot.send_message(call.from_user.id, text, parse_mode="HTML")
    
    # Foydalanuvchiga xabar
    try:
        text_user = "✅ <b>Siz 1 oylik tolov qildingiz!</b>\n\n"
        text_user += f"📅 Tugash sanasi: {end_date[:10]}\n"
        text_user += f"💰 Oylik to'lov: 15,000 so'm\n\n"
        text_user += "Endi siz barcha xizmatlardan foydalana olasiz!"
        
        from utils import user_main_menu
        
        bot.send_message(int(user_id), text_user, parse_mode="HTML", reply_markup=user_main_menu())
    except Exception as e:
        logger.exception(f"User ga xabar yuborishda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_payment")
def cancel_payment_callback(call):
    """To'lovni bekor qilish"""
    bot.answer_callback_query(call.id)
    
    state = user_state.get(call.from_user.id, {})
    payment_id = state.get("payment_id")
    
    if payment_id:
        query_db("DELETE FROM payments WHERE id = ? AND status = 'pending'", (payment_id,))
    
    user_state.pop(call.from_user.id, None)
    
    text = "❌ <b>To'lov bekor qilindi</b>"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="payment_menu"))
    
    bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "payment_menu")
def payment_menu_callback(call):
    """To'lov menyusiga qaytish"""
    bot.answer_callback_query(call.id)
    show_payment_menu(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu_callback(call):
    """Bosh menyuya qaytish"""
    bot.answer_callback_query(call.id)
    from utils import user_main_menu
    from handlers.payment_handlers import check_subscription
    
    # To'lov tekshirish
    sub = check_subscription(str(call.from_user.id))
    
    if sub["active"]:
        bot.send_message(call.from_user.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    else:
        # To'lov qilmagan bo'lsa, faqat to'lov tugmasi
        text = "❌ <b>To'lov qilmagansiz!</b>\n\nIltimos, hisobingizni to'ldiring."
        payment_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        payment_kb.add("💳 To'lov")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Hisobni to'ldirish", callback_data="topup_account"))
        
        bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=payment_kb)
        bot.send_message(call.from_user.id, "Yoki pastdagi tugmani bosing:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "renew_subscription")
def renew_subscription_callback(call):
    """Obunani yangilash"""
    bot.answer_callback_query(call.id)
    topup_account_callback(call)

