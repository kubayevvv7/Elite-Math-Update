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
│   ├── homework_handlers.py # Uyga vazifa handlerlari
│   └── payment_handlers.py # To'lov tizimi handlerlari
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

### handlers/payment_handlers.py
- To'lov menyusi (obuna statusi)
- Karta raqamni yuborish
- To'lov tekshirish oqimi
- Admin to'lovni tasdiqlash/rad etish
- Oylik obuna faollashtiruv (30 kun)
- Obunani yangilash

### main.py
- Botni ishga tushirish
- Signal handling
- Threading (viktorina dispatcher)
- Polling/webhook sozlash

## To'lov Tizimi (Payment System)

### Xususiyatlar:
- **Oylik obuna**: 15,000 so'm
- **Obuna muddati**: 30 kun
- **Bot kartalari**: Admin tarafidan qo'shiladi va boshqariladi
- **To'lov verifikatsiyasi**: Admin tarafidan qo'l bilan tekshiriladi
- **Avtomatik mudda**: 30 kun keyinida avtomatik deaktiv bo'ladi

### Qo'llanma:

**1. Admin uchun - Karta qo'shish:**
```
/add_card 9860 1234 5678 9012 Egasi BankNomi
Format: /add_card XXXXXX XXXXXX XXXXXX XXXXXX Egasi Bank
Misol: /add_card 9860 1234 5678 9012 Ali Uzbqazo'q
```

**2. Admin uchun - Karta faolligini o'zgartirish:**
```
/toggle_card ID
Misol: /toggle_card 1
```

**3. Admin uchun - Kartani o'chirish:**
```
/delete_card ID
Misol: /delete_card 1
```

**4. User uchun - To'lov qilish:**
- 💳 To'lov tugmasini bosish
- Karta raqamini ko'chib olish
- Shu kartaga 15,000 so'm tashash
- "✅ Pul tashtim" tugmasini bosish
- Admin tekshiradi va tasdiqlaydi
- 30 kunga obuna faollashtiriladi

**5. Admin uchun - To'lovni tasdiqlash:**
- Admin bildirishnomani oladi
- ✅ Tasdiqlash tugmasini bosadi
- Foydalanuvchiga 30 kunlik obuna beriladi
- User automatik obuna statusini oladi

### Database Jadvallar:

- **bot_cards**: Bot kartalarini saqlash
  - id, card_number, card_owner, bank_name, is_active
  
- **payments**: To'lov yozuvlari
  - id, user_id, username, student_name, card_number, status, payment_date, verified_date, verified_by
  
- **subscriptions**: Oylik obunalar
  - id, user_id, username, student_name, subscription_type, price, start_date, end_date, is_active, payment_id

### Botni Ishga Tushirish

```bash
python main.py
```



