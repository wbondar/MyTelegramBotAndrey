import os
import logging
import random
import requests
from datetime import time
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    JobQueue,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения
OAUTH_TOKEN = os.getenv('OAUTH_TOKEN')  # Токен OAuth
FOLDER_ID = os.getenv('FOLDER_ID')  # Идентификатор каталога
TELEGRAM_KEY = os.getenv('TELEGRAM_KEY')  # Токен Telegram-бота

API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

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

application = None  # Глобальная переменная для доступа к application


def get_iam_token():
    """Получение IAM-токена для авторизации в Yandex Cloud."""
    if not OAUTH_TOKEN:
        logger.error("Ошибка: OAUTH_TOKEN не установлен!")
        return None
    try:
        response = requests.post(
            'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            json={'yandexPassportOauthToken': OAUTH_TOKEN},
        )
        response.raise_for_status()
        return response.json().get('iamToken')
    except requests.RequestException as e:
        logger.error(f'Ошибка при получении IAM-токена: {e}')
        return None


async def start(update: Update, context: CallbackContext) -> None:
    """Приветственное сообщение."""
    await update.message.reply_text(
        'ОООО-о-о-о-о! Кого я вижу! Здорова, Перцы!!! Покалякаем?!'
    )
    context.user_data["history"] = []  # Сбрасываем историю


async def process_message(update: Update, context: CallbackContext) -> None:
    """Обработка сообщений пользователей и сохранение истории."""
    user_text = update.message.text
    logger.info(f'Получено сообщение от пользователя: {user_text}')

    # Отправляем сообщение о том, что ответ готовится
    waiting_message = await update.message.reply_text(
        "Не уходи никуда, Умник! Готовлю ответ на твой вопрос..."
    )
    iam_token = get_iam_token()
    if not iam_token:
        await update.message.reply_text('Ошибка авторизации в Yandex Cloud.')
        return

    # Получаем историю сообщений (20 последних)
    history = context.user_data.get("history", [])
    history.append({"role": "user", "text": user_text})
    if len(history) > MAX_HISTORY:
        history.pop(0)  # Удаляем старые сообщения

    # Запрос к Yandex GPT
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt",
        "completionOptions": {"temperature": 0.3, "maxTokens": 1000},
        "messages": [
            {"role": "system", "text": "Ты - полезный помощник и эксперт по разным вопросам."}
        ]
        + history,
    }
    try:
        response = requests.post(
            API_URL,
            headers={"Accept": "application/json", "Authorization": f"Bearer {iam_token}"},
            json=data,
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f'Ответ от Yandex GPT: {result}')
        answer = (
            result.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', 'Ошибка ответа.')
        )
    except requests.RequestException as e:
        logger.error(f'Ошибка при запросе к Yandex GPT: {e}')
        answer = 'Ошибка при обращении к Yandex GPT.'

    # Добавляем ответ бота в историю
    history.append({"role": "assistant", "text": answer})
    if len(history) > MAX_HISTORY:
        history.pop(0)

    # Сохраняем обновленную историю
    context.user_data["history"] = history

    # Удаляем сообщение "Готовлю ответ..." и отправляем ответ
    await waiting_message.delete()
    await update.message.reply_text(answer)


async def send_scheduled_message(chat_id):
    """Функция для отправки случайного сообщения в заданное время."""
    message = random.choice(AUTOMATIC_MESSAGES)
    await application.bot.send_message(chat_id=chat_id, text=message)


async def send_morning_message(chat_id):
    """Отправка утреннего сообщения."""
    await application.bot.send_message(chat_id=chat_id, text=MORNING_MESSAGE)


async def send_night_message(chat_id):
    """Отправка вечернего сообщения."""
    await application.bot.send_message(chat_id=chat_id, text=NIGHT_MESSAGE)


async def schedule_messages(update: Update, context: CallbackContext) -> None:
    """Запуск расписания автоматических сообщений."""
    chat_id = update.effective_chat.id
    job_queue = context.job_queue

    # Удаляем старые задания (чтобы не создавать дубликаты)
    for job in job_queue.jobs():
        job.schedule_removal()

    # Запускаем фиксированные сообщения в 8:00 и 22:00
    job_queue.run_daily(send_morning_message(chat_id), time(hour=8, minute=0))
    job_queue.run_daily(send_night_message(chat_id), time(hour=22, minute=0))

    # Запускаем случайные сообщения в 10:00, 12:00, 14:00, 16:00, 18:00, 20:00
    for hour in [10, 12, 14, 16, 18, 20]:
        job_queue.run_daily(send_scheduled_message(chat_id), time(hour=hour, minute=0))

    await update.message.reply_text("Расписание сообщений запущено! Теперь бот будет писать в течение дня.")


async def send_random_message(update: Update, context: CallbackContext) -> None:
    """Команда /random для отправки случайного сообщения."""
    message = random.choice(AUTOMATIC_MESSAGES)
    await update.message.reply_text(message)


def main() -> None:
    """Запуск Telegram-бота."""
    global application
    if not TELEGRAM_KEY:
        logger.error("Ошибка: TELEGRAM_KEY не установлен!")
        return
    application = Application.builder().token(TELEGRAM_KEY).http_version('1.1').build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", schedule_messages))  # Запуск расписания
    application.add_handler(CommandHandler("random", send_random_message))  # Команда /random
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_message)
    )

    logger.info("Бот запущен и ожидает сообщения...")
    application.run_polling()


if __name__ == '__main__':
    main()
