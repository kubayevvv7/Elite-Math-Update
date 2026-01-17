import signal
import sys
import threading
import logging
from config import bot, POLLING, logger
from database import init_db
# Import order matters! 
# homework_handlers and quiz_handlers must be imported before admin_handlers
# so that homework and quiz handlers are registered first and checked before admin handlers
from handlers import homework_handlers, quiz_handlers, admin_handlers, user_handlers, payment_handlers

def shutdown(signum, frame):
    logger.info("Shutting down...")
    try:
        bot.stop_polling()
    except Exception:
        pass
    sys.exit(0)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "🤖 Bot funksiyalari:\n\n"
        "👤 O'quvchilar: /start, 📝 Test topshirish, 📈 Mening natijalarim, 🎬 Videolar, 💰 Balans\n"
        "🧑‍💼 Adminlar: /admin, ➕ Test qo'shish, 📊 Natijalar, 🗑 Testni o'chirish, 🎬 Video qo'shish, 🗑 Videoni o'chirish, 🧩 Viktorina, 💰 Balans\n"
        "Qo'mondalar: /resultstoday"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga" and 
                     (m.chat.id not in user_state or 
                      m.chat.id in user_state and user_state[m.chat.id].get("step") not in 
                      ["submit_homework", "get_homework_name", "get_homework_answers", 
                       "select_homework_for_results", "delete_homework", "get_test_answers",
                       "edit_name", "get_name", "quiz_menu", "quiz_wait_image", "homework_menu",
                       "homework_admin_menu"]))
def go_back(message):
    from config import ADMIN_IDS, user_state
    from utils import admin_main_menu, user_main_menu
    
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
    else:
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    user_state.pop(message.chat.id, None)

if __name__ == "__main__":
    init_db()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Webhook ni o'chirish (agar mavjud bo'lsa)
    try:
        bot.delete_webhook()
        logger.info("✅ Webhook o'chirildi (agar mavjud bo'lsa)")
    except Exception as e:
        logger.warning(f"Webhook o'chirishda xatolik (ehtimol webhook yo'q): {e}")
    
    logger.info("🤖 Bot ishga tushdi...")
    
    dispatcher_thread = threading.Thread(target=quiz_handlers.quiz_dispatcher_loop, daemon=True)
    dispatcher_thread.start()
    logger.info("🧩 Viktorina dispatcher ishga tushdi (har 2 soatda)")
    
    if POLLING:
        while True:
            try:
                bot.polling(none_stop=True, timeout=20, long_polling_timeout=20)
            except Exception as e:
                error_msg = str(e)
                if "409" in error_msg or "Conflict" in error_msg:
                    logger.error("❌ 409 Conflict xatosi: Boshqa bot instance ishlayapti!")
                    logger.error("Iltimos, barcha bot instance larni to'xtating va qayta urinib ko'ring.")
                    logger.error("Buyruq: pkill -f 'python.*main.py' yoki barcha terminal oynalarini yoping.")
                logger.exception(f"Polling xatosi: {e}, 5 soniyadan so'ng qayta urinish...")
                import time
                time.sleep(5)
    else:
        logger.info("Webhook mode not configured. Set BOT_POLLING=1 to use polling.")

