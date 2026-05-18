import sqlite3
import os
import urllib.request
import json
import base64
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Данные для SMS Gateway Cloud Server
SMS_USERNAME = "kondornv"
SMS_PASSWORD = "6702nV794157"
SMS_CLOUD_URL = "https://api.sms-gate.app/3rdparty/v1/messages"

app_flask = Flask(__name__)

@app_flask.route('/')
def health_check():
    return "Бот ГСК работает!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
def create_database():
    conn = sqlite3.connect('gsk_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS garage_owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_name TEXT,
            first_name TEXT,
            patronymic TEXT,
            address TEXT,
            phone TEXT,
            debt REAL,
            garage_number INTEGER UNIQUE
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM garage_owners")
    if cursor.fetchone()[0] == 0:
        test_data = [
            ("Иванов", "Пётр", "Сергеевич", "ул. Ленина 12, кв. 5", "+79822082501", 12500.00, 101),
            ("Петрова", "Мария", "Ивановна", "пр. Мира 8, кв. 24", "+79195316255", -3400.50, 102),
            ("Сидоров", "Алексей", "Викторович", "ул. Гагарина 3, кв. 11", "+79028582408", 5000.00, 103),
            ("Кузнецова", "Елена", "Андреевна", "ул. Пушкина 22, кв. 7", "+7-921-456-78-90", 25600.75, 201),
            ("Михайлов", "Дмитрий", "Николаевич", "ул. Чехова 1, кв. 45", "+7-922-567-89-01", -1500.00, 202),
        ]
        cursor.executemany('''INSERT INTO garage_owners (last_name, first_name, patronymic, address, phone, debt, garage_number) VALUES (?, ?, ?, ?, ?, ?, ?)''', test_data)
        conn.commit()
    else:
        # Обновляем телефон для гаража 103 при каждом запуске
        cursor.execute("UPDATE garage_owners SET phone = '+79028582408' WHERE garage_number = 103")
        conn.commit()
    
    conn.close()

def get_owner_by_garage(garage_num):
    conn = sqlite3.connect('gsk_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_name, first_name, patronymic, address, phone, debt, garage_number FROM garage_owners WHERE garage_number = ?', (garage_num,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_all_owners():
    conn = sqlite3.connect('gsk_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_name, first_name, phone, debt, garage_number FROM garage_owners ORDER BY garage_number')
    results = cursor.fetchall()
    conn.close()
    return results

def update_debt(garage_num, new_debt):
    conn = sqlite3.connect('gsk_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE garage_owners SET debt = ? WHERE garage_number = ?', (new_debt, garage_num))
    conn.commit()
    conn.close()

# --- ФУНКЦИЯ ОТПРАВКИ СМС через SMS Gateway Cloud Server ---
def send_sms(phone_number, message):
    """Отправляет СМС через SMS Gateway Cloud Server"""
    
    # Очищаем номер телефона в формат E.164 (+7XXXXXXXXXX)
    clean_number = phone_number.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")
    if clean_number.startswith('8'):
        clean_number = '7' + clean_number[1:]
    if not clean_number.startswith('7'):
        clean_number = '7' + clean_number
    clean_number = '+' + clean_number
    
    print(f"📤 Отправка СМС на номер: {clean_number}")
    print(f"📝 Текст: {message[:50]}...")
    
    # Формируем запрос согласно документации SMS Gateway
    data = {
        "textMessage": {
            "text": message
        },
        "phoneNumbers": [clean_number]
    }
    
    # Basic Authentication
    credentials = base64.b64encode(f"{SMS_USERNAME}:{SMS_PASSWORD}".encode()).decode()
    
    try:
        req = urllib.request.Request(SMS_CLOUD_URL)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        req.add_header('Authorization', f'Basic {credentials}')
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        
        with urllib.request.urlopen(req, json_data, timeout=20) as response:
            response_text = response.read().decode('utf-8')
            print(f"✅ Ответ от сервера: {response_text}")
            print(f"✅ СМС успешно отправлено на {phone_number}")
            return True
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        print(f"❌ HTTP ошибка {e.code}: {error_body}")
        if e.code == 401:
            print("   Неправильный логин или пароль!")
        elif e.code == 402:
            print("   Недостаточно средств на счете! Пополните баланс в приложении.")
        elif e.code == 403:
            print("   Доступ запрещён. Проверьте подписку.")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Ошибка подключения: {e.reason}")
        print("   Проверьте интернет-соединение")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# --- ОБРАБОТЧИКИ КОМАНД БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск по номеру гаража", callback_data='search')],
        [InlineKeyboardButton("📋 Список всех владельцев", callback_data='list')],
        [InlineKeyboardButton("✏️ Изменить задолженность", callback_data='edit')],
        [InlineKeyboardButton("📱 Отправить СМС должнику", callback_data='sms')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏢 *ГСК - Учёт задолженностей*\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'search':
        await query.edit_message_text("Введите номер гаража:")
        context.user_data['action'] = 'search'
    
    elif query.data == 'list':
        owners = get_all_owners()
        if not owners:
            await query.edit_message_text("Нет данных о владельцах.")
            return
        
        message = "📋 *Список владельцев:*\n\n"
        for owner in owners:
            last_name, first_name, phone, debt, garage_num = owner
            debt_symbol = "🔴" if debt > 0 else "🟢" if debt < 0 else "⚪"
            phone_display = phone if phone else "не указан"
            message += f"*№{garage_num}*: {last_name} {first_name}\n📞 {phone_display} | {debt_symbol} {abs(debt):,.2f} руб.\n\n"
            if len(message) > 3900:
                await query.edit_message_text(message, parse_mode='Markdown')
                message = ""
        
        if message:
            await query.edit_message_text(message, parse_mode='Markdown')
        
        # Показываем меню снова
        keyboard = [
            [InlineKeyboardButton("🔍 Поиск", callback_data='search')],
            [InlineKeyboardButton("📱 Отправить СМС", callback_data='sms')],
            [InlineKeyboardButton("✏️ Изменить долг", callback_data='edit')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите дальнейшее действие:", reply_markup=reply_markup)
    
    elif query.data == 'edit':
        await query.edit_message_text("Введите номер гаража для изменения долга:")
        context.user_data['action'] = 'edit_garage'
    
    elif query.data == 'sms':
        await query.edit_message_text("Введите номер гаража должника:")
        context.user_data['action'] = 'sms_garage'

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    action = context.user_data.get('action')
    
    if action == 'search':
        try:
            garage_num = int(text)
            owner = get_owner_by_garage(garage_num)
            if owner:
                last_name, first_name, patronymic, address, phone, debt, garage_num = owner
                debt_status = "🔴 ДОЛЖЕН" if debt > 0 else "🟢 ПЕРЕПЛАТА" if debt < 0 else "⚪ РАСЧЁТЫ УРЕГУЛИРОВАНЫ"
                message = f"🏢 *Гараж №{garage_num}*\n\n👤 *Владелец:* {last_name} {first_name} {patronymic}\n📍 *Адрес:* {address}\n📞 *Телефон:* {phone}\n💰 *Задолженность:* {abs(debt):,.2f} руб.\n📊 *Статус:* {debt_status}"
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Гараж №{garage_num} не найден")
        except ValueError:
            await update.message.reply_text("❌ Введите корректный номер гаража")
        
        await start(update, context)
        context.user_data['action'] = None
    
    elif action == 'edit_garage':
        try:
            garage_num = int(text)
            owner = get_owner_by_garage(garage_num)
            if owner:
                context.user_data['edit_garage_num'] = garage_num
                context.user_data['action'] = 'edit_amount'
                await update.message.reply_text(
                    f"📊 *Гараж №{garage_num}*\n"
                    f"Текущий долг: *{owner[5]:,.2f} руб.*\n\n"
                    f"Введите новую сумму долга:\n"
                    f"(отрицательное число - переплата, 0 - расчёты урегулированы)",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(f"❌ Гараж №{garage_num} не найден")
                context.user_data['action'] = None
        except ValueError:
            await update.message.reply_text("❌ Введите корректный номер гаража")
    
    elif action == 'edit_amount':
        try:
            new_debt = float(text.replace(',', '.'))
            garage_num = context.user_data.get('edit_garage_num')
            update_debt(garage_num, new_debt)
            
            await update.message.reply_text(
                f"✅ *Задолженность обновлена!*\n\n"
                f"🏢 Гараж №{garage_num}\n"
                f"💰 Новая сумма: *{abs(new_debt):,.2f} руб.*",
                parse_mode='Markdown'
            )
            
            context.user_data['action'] = None
            await start(update, context)
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число")
    
    elif action == 'sms_garage':
        try:
            garage_num = int(text)
            
            owner = get_owner_by_garage(garage_num)
            if not owner:
                await update.message.reply_text(f"❌ Гараж №{garage_num} не найден")
                await start(update, context)
                context.user_data['action'] = None
                return
            
            phone = owner[4]
            if not phone or phone.strip() == "":
                await update.message.reply_text(f"❌ У владельца гаража №{garage_num} не указан номер телефона")
                await start(update, context)
                context.user_data['action'] = None
                return
            
            context.user_data['sms_garage_num'] = garage_num
            context.user_data['action'] = 'sms_text'
            
            last_name, first_name, _, _, phone, debt, _ = owner
            debt_abs = abs(debt)
            debt_status = "должен" if debt > 0 else "имеет переплату" if debt < 0 else "расчёты урегулированы"
            
            await update.message.reply_text(
                f"📱 *Отправка СМС*\n\n"
                f"🏢 Гараж №{garage_num}\n"
                f"👤 Владелец: {last_name} {first_name}\n"
                f"📞 Телефон: {phone}\n"
                f"💰 Сумма: {debt_abs:.2f} руб. ({debt_status})\n\n"
                f"✏️ Введите текст СМС-сообщения:",
                parse_mode='Markdown'
            )
            
            # Предлагаем шаблон
            template = f"Уважаемый(ая) {last_name} {first_name}! Напоминаем, что задолженность за гараж №{garage_num} составляет {debt_abs:.2f} руб. Просим оплатить до 25.05.2026."
            await update.message.reply_text(
                f"💡 *Пример текста:*\n`{template}`\n\n"
                f"Отправьте свой текст, или просто скопируйте этот, заменив сумму/дату.",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Введите корректный номер гаража")
    
    elif action == 'sms_text':
        sms_text = text.strip()
        garage_num = context.user_data.get('sms_garage_num')
        
        if not sms_text:
            await update.message.reply_text("❌ Текст сообщения не может быть пустым")
            return
        
        owner = get_owner_by_garage(garage_num)
        if owner:
            phone = owner[4]
            await update.message.reply_text(f"⏳ Отправка СМС на номер {phone}...")
            
            success = send_sms(phone, sms_text)
            
            if success:
                await update.message.reply_text(f"✅ СМС успешно отправлено на номер {phone}\n\n📝 Текст: {sms_text[:100]}{'...' if len(sms_text) > 100 else ''}")
            else:
                await update.message.reply_text(
                    f"❌ *Не удалось отправить СМС*\n\n"
                    f"📞 Номер: {phone}\n"
                    f"🔧 Возможные причины:\n"
                    f"• Недостаточно средств на балансе в приложении SMS Gateway\n"
                    f"• Нет интернет-соединения\n"
                    f"• Неправильный логин/пароль\n\n"
                    f"💡 Проверьте статус в приложении SMS Gateway (должен быть 'Online')",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text("❌ Ошибка: владелец не найден")
        
        context.user_data['action'] = None
        await start(update, context)

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🤖 Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    print("🚀 Запуск бота...")
    create_database()
    print("✅ База данных создана/проверена")
    print(f"📱 SMS Gateway аккаунт: {SMS_USERNAME}")
    print(f"🔑 Cloud Server URL: {SMS_CLOUD_URL}")
    
    # Запускаем Flask в отдельном потоке (для health check)
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Запускаем бота
    run_bot()