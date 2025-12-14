# Telegram Bot - Kod Strukturasi

Bu bot kodi mantiqiy qismlarga bo'lingan va har bir qism alohida faylda joylashgan.

## Fayl Strukturasi

```
bott/
├── config.py              # Konfiguratsiya, importlar va bot instance
├── database.py            # Barcha database funksiyalari
├── utils.py               # Utility funksiyalar va menu generatorlar
├── main.py                # Asosiy fayl, botni ishga tushirish
├── handlers/
│   ├── __init__.py        # Handlers package
│   ├── admin_handlers.py  # Admin handlerlari
│   ├── user_handlers.py   # User handlerlari
│   ├── quiz_handlers.py   # Viktorina handlerlari
│   └── homework_handlers.py # Uyga vazifa handlerlari
└── jjjj.py                # Eski fayl (eski kod)
```

## Fayllar Tavsifi

### config.py
- Bot token va konfiguratsiya sozlamalari
- Bot instance yaratish
- Global state (user_state, user_profiles)
- Logging sozlash

### database.py
- Database yaratish va yangilash (init_db)
- Barcha database operatsiyalari (query_db)
- User profile funksiyalari
- Quiz funksiyalari
- Balance funksiyalari

### utils.py
- Test ID generatsiya
- Menu generatorlar (admin_main_menu, user_main_menu)
- Javoblarni ajratish funksiyalari
- Admin balans ko'rsatish

### handlers/admin_handlers.py
- Admin komandalari va handlerlari
- Test qo'shish/o'chirish
- Video qo'shish/o'chirish
- Natijalarni ko'rish
- Balans boshqaruvi

### handlers/user_handlers.py
- User komandalari va handlerlari
- Test topshirish
- Natijalarni ko'rish
- Ismni tahrirlash
- Videolarni ko'rish

### handlers/quiz_handlers.py
- Viktorina savollari boshqaruvi
- Viktorina yuborish
- Viktorina javoblarini qabul qilish
- Viktorina dispatcher (avtomatik yuborish)

### handlers/homework_handlers.py
- Uyga vazifa qo'shish/o'chirish (admin)
- Uyga vazifa topshirish (user)
- Uyga vazifa natijalari

### main.py
- Botni ishga tushirish
- Signal handling
- Threading (viktorina dispatcher)
- Polling/webhook sozlash

## Botni Ishga Tushirish

```bash
python main.py
```



