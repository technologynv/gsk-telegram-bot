# ==================================================
# 1. Твой оригинальный код бота (бот, обработчики и т.д.)
# ==================================================
import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- ЗАМЕНИ НА СВОЙ ТОКЕН ---
BOT_TOKEN = "8869399865:AAGi1X5CE1RArnz4XJRgXgaQkWKz99UpVzY"

# Пример простого обработчика
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот, работаю на Render.")

def run_bot_polling():
    """Запускает поллинг бота (твоя логика)"""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # Добавь сюда свои обработчики
    app.run_polling()

# ==================================================
# 2. Веб-сервер (чтобы Render не ругался на порты)
# ==================================================
from flask import Flask
import threading

web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "✅ Бот работает", 200

def run_webserver():
    """Запускает веб-сервер на порту из переменной PORT (Render подставляет)"""
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================================================
# 3. Запуск обоих процессов в одном контейнере
# ==================================================
if __name__ == "__main__":
    # Запускаем веб-сервер в фоновом потоке
    web_thread = threading.Thread(target=run_webserver, daemon=True)
    web_thread.start()

    # Запускаем бота (основной поток)
    run_bot_polling()