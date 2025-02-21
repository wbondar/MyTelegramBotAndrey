import os
import logging
import random
import requests
from datetime import time
from pytz import timezone
from telegram import Update
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


def get_iam_token():
    """Получение IAM-токена для авторизации в Yandex Cloud."""
    if not OAUTH_TOKEN:
        logger.error("Ошибка: OAUTH_TOKEN не установлен!")
        return None

    try:
        response = requests.post(
            'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            json={'yandexPassportOauthToken': OAUTH_TOKEN}
        )
        response.raise_for_status()
        return response.json().get('iamToken')
    except requests.RequestException as e:
        logger.error(f'Ошибка при получении IAM-токена: {e}')
        return None


async def start(update: Update, context: CallbackContext) -> None:
    """Приветственное сообщение."""
    await update.message.reply_text('ОООО-о-о-о-о! Кого я вижу! Здорова, Перцы!!! Покалякаем?!')
    context.user_data["history"] = []  # Сбрасываем историю


async def process_message(update: Update, context: CallbackContext) -> None:
    """Обработка сообщений пользователей и сохранение истории."""
    user_text = update.message.text
    logger.info(f'Получено сообщение от пользователя: {user_text}')

    waiting_message = await update.message.reply_text("Не уходи никуда, Умник! Готовлю ответ на твой вопрос...")

    iam_token = get_iam_token()
    if not iam_token:
        await update.message.reply_text('Ошибка авторизации в Yandex Cloud.')
        return

    history = context.user_data.get("history", [])
    history.append({"role": "user", "text": user_text})
    if len(history) > MAX_HISTORY:
        history.pop(0)

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt",
        "completionOptions": {"temperature": 0.3, "maxTokens": 1000},
        "messages": [{"role": "system", "text": "Ты - полезный помощник и эксперт по разным вопросам."}] + history
    }

    try:
        response = requests.post(
            API_URL,
            headers={"Accept": "application/json", "Authorization": f"Bearer {iam_token}"},
            json=data
        )
        response.raise_for_status()
        result = response.json()
        answer = result.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', 'Ошибка ответа.')
    except requests.RequestException as e:
        logger.error(f'Ошибка при запросе к Yandex GPT: {e}')
        answer = 'Ошибка при обращении к Yandex GPT.'

    history.append({"role": "assistant", "text": answer})
    if len(history) > MAX_HISTORY:
        history.pop(0)

    context.user_data["history"] = history
    await waiting_message.delete()
    await update.message.reply_text(answer)


async def send_scheduled_message(context: CallbackContext) -> None:
    """Отправка случайного сообщения."""
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
        return

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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))

    if schedule_messages(application.job_queue):
        application.bot.send_message(chat_id=CHAT_ID, text="Расписание сообщений запущено!")

    logger.info("Бот запущен и ожидает сообщения...")
    application.run_polling()


if __name__ == '__main__':
    main()
