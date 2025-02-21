import os
import logging
import random
import requests
from datetime import time
from pytz import timezone
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, JobQueue

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
OAUTH_TOKEN = os.getenv('OAUTH_TOKEN')  # Токен OAuth
FOLDER_ID = os.getenv('FOLDER_ID')  # Идентификатор каталога
TELEGRAM_KEY = os.getenv('TELEGRAM_KEY')  # Токен Telegram-бота
CHAT_ID = os.getenv('CHAT_ID')  # ID чата, где бот должен отправлять сообщения

API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Часовой пояс Москвы
MSK_TZ = timezone('Europe/Moscow')

# Список случайных сообщений
AUTOMATIC_MESSAGES = [
    "Андрей, держись бодрей! А то Петька отмерзнет!",
    "Ну что, заскучали? Так займитесь делом!",
    "Пора бы и за работу, но лучше выпейте по 100 грамм!",
    "Кто охотчий до еды, пусть пожалует сюды...",
    "Чем вы вообще вот занимаетесь, что я должен вас все время контролировать?",
    "Андрей! Прекрати ЭТО делать! Коллеги могут увидеть!",
    "Шайтаны, ну вы чего? Кто это опять такую кучу навалял?!",
    "Саня, расскажи про БАБ и про женщин!",
    "Вадик, проснись! Тебя все ищут!",
    "Перцы, рассказывайте кому что снилось сегодня?",
    "МЕРНЕМ ДЖАНИД - значит на армянском (Дай мне умереть на твоем теле!)",
    "- Эх Яблочко да на тарелочке - Погибай же ты КОНТРА в перестрелочке!",
]

# Фиксированные сообщения
MORNING_MESSAGE = "Вставайте, Засранцы и давайте работайте над собой и на державу!"
NIGHT_MESSAGE = "Пора спать, Засранцы! Завтра все опять на работу, не проспите!"

MAX_HISTORY = 20  # Храним 20 последних сообщений


async def start(update: Update, context: CallbackContext) -> None:
    """Приветственное сообщение с кнопкой меню."""
    keyboard = [["/random", "/schedule"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "ОООО-о-о-о-о! Кого я вижу! Здорова, Перцы!!! Покалякаем?!\n\n"
        "Доступные команды:\n"
        "🔹 /random — случайное сообщение\n"
        "🔹 /schedule — проверить статус расписания\n",
        reply_markup=reply_markup
    )
    context.user_data["history"] = []  # Сбрасываем историю


async def send_random_message(update: Update, context: CallbackContext) -> None:
    """Отправляет случайное сообщение при команде /random."""
    message = random.choice(AUTOMATIC_MESSAGES)
    await update.message.reply_text(message)


async def check_schedule(update: Update, context: CallbackContext) -> None:
    """Проверяет, включено ли расписание."""
    await update.message.reply_text("✅ Автоматическое расписание сообщений активно и работает!")


async def send_scheduled_message(context: CallbackContext) -> None:
    """Отправка случайного сообщения по расписанию."""
    chat_id = context.job.context
    message = random.choice(AUTOMATIC_MESSAGES)
    await context.bot.send_message(chat_id=chat_id, text=message)


async def send_morning_message(context: CallbackContext) -> None:
    """Отправка утреннего сообщения."""
    chat_id = context.job.context
    await context.bot.send_message(chat_id=chat_id, text=MORNING_MESSAGE)


async def send_night_message(context: CallbackContext) -> None:
    """Отправка вечернего сообщения."""
    chat_id = context.job.context
    await context.bot.send_message(chat_id=chat_id, text=NIGHT_MESSAGE)


def schedule_messages(job_queue: JobQueue):
    """Настройка автоматического расписания."""
    if not CHAT_ID:
        logger.error("Ошибка: CHAT_ID не установлен!")
        return False

    job_queue.run_daily(send_morning_message, time(hour=8, minute=0, tzinfo=MSK_TZ), context=CHAT_ID)
    job_queue.run_daily(send_night_message, time(hour=22, minute=0, tzinfo=MSK_TZ), context=CHAT_ID)

    for hour in [10, 12, 14, 16, 18, 20]:
        job_queue.run_daily(send_scheduled_message, time(hour=hour, minute=0, tzinfo=MSK_TZ), context=CHAT_ID)

    return True


def main() -> None:
    """Запуск Telegram-бота."""
    if not TELEGRAM_KEY:
        logger.error("Ошибка: TELEGRAM_KEY не установлен!")
        return

    application = Application.builder().token(TELEGRAM_KEY).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("random", send_random_message))
    application.add_handler(CommandHandler("schedule", check_schedule))

    if schedule_messages(application.job_queue):
        application.bot.send_message(chat_id=CHAT_ID, text="✅ Расписание сообщений успешно запущено!")

    logger.info("Бот запущен и ожидает сообщения...")
    application.run_polling()


if __name__ == '__main__':
    main()
