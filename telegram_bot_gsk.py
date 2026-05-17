import sqlite3
import os
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

app_flask = Flask(__name__)

@app_flask.route('/')
def health_check():
    return "Бот ГСК работает!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

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
            ("Иванов", "Пётр", "Сергеевич", "ул. Ленина 12, кв. 5", "+7-911-123-45-67", 12500.00, 101),
            ("Петрова", "Мария", "Ивановна", "пр. Мира 8, кв. 24", "+7-912-234-56-78", -3400.50, 102),
            ("Сидоров", "Алексей", "Викторович", "ул. Гагарина 3, кв. 11", "+7-913-345-67-89", 0.00, 103),
            ("Кузнецова", "Елена", "Андреевна", "ул. Пушкина 22, кв. 7", "+7-921-456-78-90", 25600.75, 201),
            ("Михайлов", "Дмитрий", "Николаевич", "ул. Чехова 1, кв. 45", "+7-922-567-89-01", -1500.00, 202),
        ]
        cursor.executemany('''INSERT INTO garage_owners (last_name, first_name, patronymic, address, phone, debt, garage_number) VALUES (?, ?, ?, ?, ?, ?, ?)''', test_data)
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск по номеру гаража", callback_data='search')],
        [InlineKeyboardButton("📋 Список всех владельцев", callback_data='list')],
        [InlineKeyboardButton("✏️ Изменить задолженность", callback_data='edit')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏢 *ГСК - Учёт задолженностей*\n\nВыберите действие:", reply_markup=reply_markup, parse_mode='Markdown')

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
            message += f"*№{garage_num}*: {last_name} {first_name}\n📞 {phone} | {debt_symbol} {abs(debt):,.2f} руб.\n\n"
        await query.edit_message_text(message, parse_mode='Markdown')
        await start(update, context)
    elif query.data == 'edit':
        await query.edit_message_text("Введите номер гаража для изменения долга:")
        context.user_data['action'] = 'edit_garage'

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
                await update.message.reply_text(f"📊 *Гараж №{garage_num}*\nТекущий долг: *{owner[5]:,.2f} руб.*\n\nВведите новую сумму долга (отрицательное число - переплата, 0 - расчёты урегулированы):", parse_mode='Markdown')
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
            await update.message.reply_text(f"✅ *Задолженность обновлена!*\n\n🏢 Гараж №{garage_num}\n💰 Новая сумма: *{abs(new_debt):,.2f} руб.*", parse_mode='Markdown')
            context.user_data['action'] = None
            await start(update, context)
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число")

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