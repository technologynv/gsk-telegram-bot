import sqlite3
import os
import urllib.parse
import urllib.request
import json
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")

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
            ("Сидоров", "Алексей", "Викторович", "ул. Гагарина 3, кв. 11", "+7-913-345-67-89", 0.00, 103),
            ("Кузнецова", "Елена", "Андреевна", "ул. Пушкина 22, кв. 7", "+7-921-456-78-90", 25600.75, 201),
            ("Михайлов", "Дмитрий", "Николаевич", "ул. Чехова 1, кв. 45", "+7-922-567-89-01", -1500.00, 202),
        ]
        cursor.executemany('''INSERT INTO garage_owners (last_name, first_name, patronymic, address, phone, debt, garage_number) VALUES (?, ?, ?, ?, ?, ?, ?)''', test_data)
        conn.commit()
    else:
        cursor.execute("UPDATE garage_owners SET phone = '+79822082501' WHERE garage_number = 101")
        cursor.execute("UPDATE garage_owners SET phone = '+79195316255' WHERE garage_number = 102")
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

# --- ФУНКЦИЯ ОТПРАВКИ СМС (через urllib, без requests) ---
def send_sms(phone_number, message):
    """Отправляет СМС через sms.ru без использования сторонних библиотек"""
    if not SMS_API_KEY:
        print("❌ SMS_API_KEY не задан")
        return False
    
    clean_number = phone_number.replace("+", "").replace("-", "").replace(" ", "")
    encoded_message = urllib.parse.quote(message)
    url = f"https://sms.ru/sms/send?api_id={SMS_API_KEY}&to={clean_number}&msg={encoded_message}&json=1"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("status") == "OK":
                print(f"✅ СМС отправлено на {phone_number}")
                return True
            else:
                print(f"❌ Ошибка СМС: {data}")
                return False
    except Exception as e:
        print(f"❌ Ошибка при отправке СМС: {e}")
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
            phone_display = phone if garage_num in [101, 102] else "скрыт"
            message += f"*№{garage_num}*: {last_name} {first_name}\n📞 {phone_display} | {debt_symbol} {abs(debt):,.2f} руб.\n\n"
            if len(message) > 3900:
                await query.edit_message_text(message, parse_mode='Markdown')
                message = ""
        
        if message:
            await query.edit_message_text(message, parse_mode='Markdown')
        
        await start(update, context)
    
    elif query.data == 'edit':
        await query.edit_message_text("Введите номер гаража для изменения долга:")
        context.user_data['action'] = 'edit_garage'
    
    elif query.data == 'sms':
        await query.edit_message_text("Введите номер гаража должника (101 или 102):")
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
            if garage_num not in [101, 102]:
                await update.message.reply_text("❌ СМС можно отправить только для гаражей 101 и 102")
                await start(update, context)
                context.user_data['action'] = None
                return
            
            owner = get_owner_by_garage(garage_num)
            if not owner:
                await update.message.reply_text(f"❌ Гараж №{garage_num} не найден")
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
                f"Введите текст СМС-сообщения:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Введите корректный номер гаража")
    
    elif action == 'sms_text':
        sms_text = text
        garage_num = context.user_data.get('sms_garage_num')
        owner = get_owner_by_garage(garage_num)
        
        if owner:
            phone = owner[4]
            success = send_sms(phone, sms_text)
            if success:
                await update.message.reply_text(f"✅ СМС успешно отправлено на номер {phone}")
            else:
                await update.message.reply_text(
                    f"❌ Не удалось отправить СМС.\n\n"
                    f"Проверьте API ключ sms.ru или отправьте сообщение вручную на номер {phone}"
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
    print("🚀 Запуск бота и веб-сервера...")
    create_database()
    print("✅ База данных создана/проверена")
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()