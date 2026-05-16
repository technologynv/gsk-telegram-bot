import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes
from telegram.ext import filters

# === ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ОТ @BotFather ===
BOT_TOKEN = "8869399865:AAGi1X5CE1RArnz4XJRgXgaQkWKz99UpVzY"  # ← ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ТОКЕН!

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
    
    # Добавляем тестовые данные, если таблица пуста
    cursor.execute("SELECT COUNT(*) FROM garage_owners")
    if cursor.fetchone()[0] == 0:
        test_data = [
            ("Иванов", "Пётр", "Сергеевич", "ул. Ленина 12, кв. 5", "+7-911-123-45-67", 12500.00, 101),
            ("Петрова", "Мария", "Ивановна", "пр. Мира 8, кв. 24", "+7-912-234-56-78", -3400.50, 102),
            ("Сидоров", "Алексей", "Викторович", "ул. Гагарина 3, кв. 11", "+7-913-345-67-89", 0.00, 103),
            ("Кузнецова", "Елена", "Андреевна", "ул. Пушкина 22, кв. 7", "+7-921-456-78-90", 25600.75, 201),
            ("Михайлов", "Дмитрий", "Николаевич", "ул. Чехова 1, кв. 45", "+7-922-567-89-01", -1500.00, 202),
            ("Фёдорова", "Анна", "Павловна", "ул. Новая 15, кв. 3", "+7-931-678-90-12", 890.30, 203),
            ("Васильев", "Игорь", "Алексеевич", "ул. Советская 7, кв. 19", "+7-951-789-01-23", 4250.00, 301),
            ("Морозов", "Владимир", "Евгеньевич", "ул. Лесная 4, кв. 22", "+7-952-890-12-34", -2200.00, 302),
            ("Волкова", "Татьяна", "Сергеевна", "ул. Садовая 9, кв. 1", "+7-953-901-23-45", 13200.00, 303),
            ("Зайцев", "Антон", "Романович", "ул. Дружбы 18, кв. 6", "+7-961-012-34-56", 675.40, 401),
            ("Соколова", "Наталья", "Михайловна", "ул. Восточная 2, кв. 14", "+7-962-123-45-67", -5000.00, 402),
            ("Лебедев", "Константин", "Борисович", "ул. Западная 11, кв. 8", "+7-963-234-56-78", 3000.00, 403),
            ("Новиков", "Максим", "Дмитриевич", "ул. Северная 5, кв. 12", "+7-964-345-67-89", 18750.25, 501),
            ("Козлова", "Ольга", "Анатольевна", "ул. Южная 7, кв. 5", "+7-965-456-78-90", -800.00, 502),
            ("Егоров", "Никита", "Валерьевич", "ул. Центральная 1, кв. 31", "+7-966-567-89-01", 0.00, 503),
            ("Павлова", "Ирина", "Владимировна", "ул. Московская 10, кв. 16", "+7-967-678-90-12", 9400.00, 601),
            ("Семёнов", "Артём", "Олегович", "ул. Кирова 3, кв. 27", "+7-968-789-01-23", -4200.00, 602),
            ("Андреев", "Роман", "Игоревич", "ул. Парковая 6, кв. 44", "+7-969-890-12-34", 5600.00, 603),
            ("Тимофеева", "Светлана", "Николаевна", "ул. Берёзовая 17, кв. 9", "+7-981-901-23-45", -11200.00, 701),
            ("Григорьев", "Евгений", "Александрович", "ул. Речная 21, кв. 13", "+7-982-012-34-56", 3050.50, 702),
        ]
        cursor.executemany('''
            INSERT INTO garage_owners (last_name, first_name, patronymic, address, phone, debt, garage_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', test_data)
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

# --- ОБРАБОТЧИКИ КОМАНД БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск по номеру гаража", callback_data='search')],
        [InlineKeyboardButton("📋 Список всех владельцев", callback_data='list')],
        [InlineKeyboardButton("✏️ Изменить задолженность", callback_data='edit')],
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
            message += f"*№{garage_num}*: {last_name} {first_name}\n📞 {phone} | {debt_symbol} {abs(debt):,.2f} руб.\n\n"
            if len(message) > 3900:  # Telegram лимит
                await query.edit_message_text(message, parse_mode='Markdown')
                message = ""
        
        if message:
            await query.edit_message_text(message, parse_mode='Markdown')
        
        # Показываем меню снова
        keyboard = [
            [InlineKeyboardButton("🔍 Поиск", callback_data='search')],
            [InlineKeyboardButton("📋 Список", callback_data='list')],
            [InlineKeyboardButton("✏️ Изменить долг", callback_data='edit')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
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
                if debt > 0:
                    debt_status = "🔴 ДОЛЖЕН КООПЕРАТИВУ"
                elif debt < 0:
                    debt_status = "🟢 КООПЕРАТИВ ДОЛЖЕН"
                else:
                    debt_status = "⚪ РАСЧЁТЫ УРЕГУЛИРОВАНЫ"
                
                message = f"""
🏢 *Гараж №{garage_num}*

👤 *Владелец:* {last_name} {first_name} {patronymic}
📍 *Адрес:* {address}
📞 *Телефон:* {phone}

💰 *Задолженность:* {abs(debt):,.2f} руб.
📊 *Статус:* {debt_status}
"""
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Гараж №{garage_num} не найден")
        except ValueError:
            await update.message.reply_text("❌ Введите корректный номер гаража (только цифры)")
        
        # Возвращаем меню
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
                    f"(отрицательное число - переплата, например: -5000)\n"
                    f"(0 - расчёты урегулированы)",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(f"❌ Гараж №{garage_num} не найден")
                context.user_data['action'] = None
        except ValueError:
            await update.message.reply_text("❌ Введите корректный номер гаража (только цифры)")
    
    elif action == 'edit_amount':
        try:
            new_debt = float(text.replace(',', '.'))
            garage_num = context.user_data.get('edit_garage_num')
            update_debt(garage_num, new_debt)
            
            if new_debt > 0:
                status = "🔴 должен кооперативу"
            elif new_debt < 0:
                status = "🟢 переплата (кооператив должен)"
            else:
                status = "⚪ расчёты урегулированы"
            
            await update.message.reply_text(
                f"✅ *Задолженность обновлена!*\n\n"
                f"🏢 Гараж №{garage_num}\n"
                f"💰 Новая сумма: *{abs(new_debt):,.2f} руб.*\n"
                f"📊 Статус: {status}",
                parse_mode='Markdown'
            )
            context.user_data['action'] = None
            await start(update, context)
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число (например: 1500 или -500)")

def main():
    print("🚀 Запуск бота...")
    create_database()
    print("✅ База данных создана/проверена")
    
    # Создаём приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🤖 Бот успешно запущен и готов к работе!")
    print(f"📱 Найдите бота в Telegram и отправьте /start")
    
    # Запускаем бота
    app.run_polling()

if __name__ == "__main__":
    main()
