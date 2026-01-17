# To'lov Tizimi (Payment System)

## 📋 Umumiy Tavsif

**Oylik obuna tizimi** foydalanuvchilarga test, uyga vazifa va videolarga kirish uchun 30 kunga ruxsat beradigan to'lov mexanizmi.

- **Narxi**: 15,000 so'm/oy
- **Muddati**: 30 kun
- **Tasdiqlanish**: Admin qo'l bilan

---

## 🏗️ Arxitektura

### Database Jadvallar

#### 1. `bot_cards` - Bot kartalar ro'yxati
```sql
CREATE TABLE bot_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_number TEXT NOT NULL,
    card_owner TEXT NOT NULL,
    bank_name TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

#### 2. `payments` - To'lov yozuvlari
```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    username TEXT,
    student_name TEXT,
    card_number TEXT,
    status TEXT DEFAULT 'pending',  -- pending, verified, rejected, cancelled
    payment_date DATETIME,
    verified_date DATETIME,
    verified_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

#### 3. `subscriptions` - Faol obunalar
```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    username TEXT,
    student_name TEXT,
    subscription_type TEXT DEFAULT 'monthly',
    price INTEGER DEFAULT 15000,
    start_date DATETIME,
    end_date DATETIME,
    is_active INTEGER DEFAULT 1,
    payment_id INTEGER REFERENCES payments(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

---

## 🔄 To'lov Oqimi (Payment Flow)

### 1️⃣ Foydalanuvchi Perspektivas

```
User Bosh Menyu
    ↓
💳 "To'lov" tugmasini bosish
    ↓
🔍 Obuna statusi tekshiriladi
    ├─→ Faol obuna → "Obunani yangilash" habarini ko'rsa
    └─→ Obuna yo'q → "💳 Hisobni to'ldirish" tugmasini bosish
    ↓
💳 KARTA RAQAMI YUBORILADI
Bot: "Bu karta raqamiga pul tashang..."
    ↓
Foydalanuvchi: Shu kartaga 15,000 so'm tashaydi
    ↓
"✅ Pul tashtim" tugmasini bosish
    ↓
⏳ Admin tekshirilishi kutilmoqda
    ├─→ Admin "✅ Tasdiqlash" → ✅ Obuna faollashtirildi (30 kun)
    └─→ Admin "❌ Rad etish" → ❌ Pul qaytarilmay tugatiladi
```

### 2️⃣ Admin Perspektivas

```
Admin Bosh Menyu
    ↓
💳 "Kartalarni boshqarish" tugmasini bosish
    ↓
Faol kartalar ro'yxati
    ├─→ /add_card 9860 1234 5678 9012 Ali Bank
    ├─→ /toggle_card 1
    └─→ /delete_card 1
    ↓
📱 To'lov Bildirishnomasi
Admin: "Yangi to'lov tekshirishi kerak"
    ├─→ ✅ Tasdiqlash
    │     ├─→ To'lov status: "verified"
    │     ├─→ Subscriptions jadvalidagi yozuv
    │     ├─→ end_date = now + 30 days
    │     └─→ User: "Siz 1 oylik tolov qildingiz!"
    │
    └─→ ❌ Rad etish
          ├─→ To'lov status: "rejected"
          └─→ User: "Sizning to'lovingiz rad etildi"
```

---

## 📱 Handler Funksiyalari

### Payment Handlers (`handlers/payment_handlers.py`)

#### `show_payment_menu(message)`
- **Vazifasi**: To'lov menyusini ko'rsatish
- **Kiritish**: User message
- **Chiqarish**: Obuna statusi va tugmalar
- **Logika**:
  - Foydalanuvchining obunasini tekshirish
  - Faol obuna bo'lsa → "🔄 Obunani yangilash" tugmasi
  - Obuna yo'q bo'lsa → "💳 Hisobni to'ldirish" tugmasi

#### `topup_account_callback(call)`
- **Vazifasi**: Karta raqamini ko'rsatish va to'lovni boshlash
- **Kiritish**: Callback query
- **Chiqarish**: Karta ma'lumotlari bilan xabar
- **Logika**:
  - Faol karta raqamini olish
  - User state'ga karta ma'lumotlarini saqlash
  - Karta raqamini ko'rsatish

#### `confirm_payment_sent_callback(call)`
- **Vazifasi**: Foydalanuvchi to'lovni amalga oshirgani haqida xabar
- **Kiritish**: Callback query
- **Chiqarish**: Admin bildirishnomasi
- **Logika**:
  - To'lov yozuvini database ga qo'shish (status: "pending")
  - Admin ga bildirishnoma yuborish
  - ✅ Tasdiqlash va ❌ Rad etish tugmalari

#### `verify_payment_callback(call)`
- **Vazifasi**: Admin to'lovni tasdiqlash
- **Kiritish**: Callback query (verify_payment:payment_id)
- **Chiqarish**: 30 kunga obuna faollashtiruvi
- **Logika**:
  - To'lov statusini "verified" ga o'zgartirish
  - Subscriptions jadvalidagi yozuvni yaratish
  - end_date = now + 30 days
  - User bildirishnomasi

#### `reject_payment_callback(call)`
- **Vazifasi**: Admin to'lovni rad etish
- **Kiritish**: Callback query (reject_payment:payment_id)
- **Chiqarish**: To'lov bekor qilish
- **Logika**:
  - To'lov statusini "rejected" ga o'zgartirish
  - User bildirishnomasi

#### `cancel_payment_callback(call)`
- **Vazifasi**: Foydalanuvchi to'lovni bekor qilish
- **Kiritish**: Callback query
- **Chiqarish**: Bekor qilish tasdiqlanishi

#### `renew_subscription_callback(call)`
- **Vazifasi**: Mavjud obunan foydalanuvchining obunasini yangilash
- **Kiritish**: Callback query
- **Chiqarish**: Yangi karta raqami va to'lov boshlash
- **Logika**:
  - Yangi to'lov yozuvini yaratish
  - Karta raqamini ko'rsatish

---

## 🔐 Xavfsizlik

### SQL Injection Zashtitasi
- Barcha SQL so'rovlari parameterlar bilan tayyorlanadi
- `query_db(sql, params)` foydalaniladi

### Ruxsat Tekshiruvi
- Admin funksiyalarida `if call.from_user.id not in ADMIN_IDS: return`
- Blok qilish va obuna tekshiruvi feature kirishida

### User State Tozalash
- To'lov jarayonidan so'ng `user_state` o'chiriladi
- Vaqtinchalik ma'lumotlar saqlanmaydi

---

## 🛠️ Tatbiq Qilish (Implementation)

### Fayl O'zgarishlari

1. **database.py** ✅
   - `bot_cards`, `payments`, `subscriptions` jadvallar

2. **payment_handlers.py** ✅
   - Barcha to'lov funksiyalari va callback handlerlari

3. **admin_handlers.py** ✅
   - Karta boshqarish komandalar:
     - `/add_card`
     - `/toggle_card`
     - `/delete_card`
     - `manage_bot_cards_menu()`

4. **user_handlers.py** ✅
   - `💳 To'lov` tugmasi uchun handler
   - Obuna tekshiruvi `submit_test_start()`ga qo'shildi

5. **homework_handlers.py** ✅
   - Obuna tekshiruvi `submit_homework_start()`ga qo'shildi

6. **utils.py** ✅
   - `admin_main_menu()` ga `💳 Kartalarni boshqarish` tugmasi
   - `user_main_menu()` ga `💳 To'lov` tugmasi

7. **main.py** ✅
   - `payment_handlers` import qilindi

---

## 📝 Admin Komandalar

### Karta Qo'shish
```
/add_card 9860 1234 5678 9012 Ali Uzbqazo'q
```

Format: `/add_card XXXXXX XXXXXX XXXXXX XXXXXX Egasi BankNomi`

### Karta Faolligini O'zgartirish
```
/toggle_card 1
```

### Kartani O'chirish
```
/delete_card 1
```

### Kartalarni Boshqarish Menyusi
```
💳 Kartalarni boshqarish (tugma bilan)
```

---

## 🧪 Testing

### Test Admin Kartasi
```
Karta: 9860 1234 5678 9012
Egasi: Elite Math Bot
Bank: O'zbekiston Milliy Banki
Status: ✅ Faol (is_active = 1)
```

### Test To'lov Oqimi
1. Admin kartasi qo'shildi ✅
2. User "💳 To'lov" tugmasini bosadi
3. Bot karta raqamini yuboradi
4. User "✅ Pul tashtim" bosadi
5. Admin bildirishnoma oladi
6. Admin "✅ Tasdiqlash" bosadi
7. User obuna faollashtiriladi (30 kun)

---

## 🚀 Deployment

Bot ishga tushirilgach:
1. **Admin** `/add_card` komandasi bilan kartalarni qo'shadi
2. **User** "💳 To'lov" tugmasini bosgach to'lov oqimi boshlashadi
3. **Admin** to'lovni tekshirib tasdiqlaydi
4. **User** avtomatik 30 kunga obuna oladi
5. **30 kunga muddati o'tgach** obuna avtomatik deaktiv bo'ladi

---

## 📊 Status Kodlari

| Status | Ma'nosi | Aksiya |
|--------|---------|--------|
| `pending` | Tekshiruv kutilmoqda | Admin tekshirasi kerak |
| `verified` | Tekshirildi, obuna faollashtirildi | Hech nima (tugallandi) |
| `rejected` | Rad etildi | User qaytadan urinishi mumkin |
| `cancelled` | Foydalanuvchi bekor qildi | Hech nima |

---

## ⚙️ Konfiguratsiya

### config.py
```python
ADMIN_IDS = [123456789, 987654321]  # Admin ID lari
```

### environment variables
```
BOT_TOKEN=your_token_here
BOT_POLLING=1
```

---

## 🔗 Bog'lanish

- **To'lovlar jadvalining e'lon/xatolar:** `payments` jadvalidagi `status` tekshiring
- **Obunalarni tekshirish:** `subscriptions` jadvalidagi `is_active` va `end_date`
- **Admin kartalar:** `bot_cards` jadvalidagi `is_active` flag

---

**Tayyorlangan**: Elite Math Bot
**Versiya**: 1.0
**O'xirgi Yangilash**: 2024
