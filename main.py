import signal
import sys
import threading
import logging
from config import bot, POLLING, logger
from database import init_db
from handlers import admin_handlers, user_handlers, quiz_handlers, homework_handlers

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

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def go_back(message):
    from config import ADMIN_IDS
    from utils import admin_main_menu, user_main_menu
    
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=admin_main_menu())
    else:
        bot.send_message(message.chat.id, "🏠 Bosh menyu", reply_markup=user_main_menu())
    from config import user_state
    user_state.pop(message.chat.id, None)

if __name__ == "__main__":
    init_db()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    logger.info("🤖 Bot ishga tushdi...")
    
    dispatcher_thread = threading.Thread(target=quiz_handlers.quiz_dispatcher_loop, daemon=True)
    dispatcher_thread.start()
    logger.info("🧩 Viktorina dispatcher ishga tushdi (har 2 soatda)")

    if POLLING:
        while True:
            try:
                bot.polling(none_stop=True, timeout=20, long_polling_timeout=20)
            except Exception as e:
                logger.exception(f"Polling xatosi: {e}, 5 soniyadan so'ng qayta urinish...")
                import time
                time.sleep(5)
    else:
        logger.info("Webhook mode not configured. Set BOT_POLLING=1 to use polling.")

