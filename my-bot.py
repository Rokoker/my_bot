from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.types.bot_command import BotCommand
from aiogram.utils.token import TokenValidationError
import asyncio
import logging
import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import openai
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage



# Логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Загружаем переменные из файла .env
load_dotenv()

OPEN_API_KEY = os.getenv("OPEN_API_KEY")
openai.api_key=OPEN_API_KEY
# Читаем настройки из окружения
DB_CONFIG = {
    'dbname': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'host': os.getenv("DB_HOST"),
    'port': os.getenv("DB_PORT"),
}

# Инициализация бота и диспетчера
try:
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
except TokenValidationError as e:
    logging.error(f"Ошибка в токене бота: {e}")
    raise

# Добавляем хранилище состояний
dp = Dispatcher(storage=MemoryStorage())

# Определяем группу состояний
class QuestionStates(StatesGroup):
    waiting_for_question = State()

router = Router()
dp.include_router(router)

# Подключение к базе данных
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG, cursor_factory=DictCursor)
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        raise

# Регистрация пользователей
@router.message(Command("register"))
async def handle_register(message: Message):
    # Проверяем, что сообщение было отправлено в ЛС
    if message.chat.type != 'private':
        await message.reply("Регистрация доступна только в личных сообщениях.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажите пароль для регистрации.")
        return

    password = args[1]
    user_id = message.from_user.id
    if password == "EbalTvoiROT":
        pass
    else:
        await message.reply("Ха, сьебал в ужасе из ЛС")
        return
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем, есть ли пользователь в базе
        cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
        if cur.fetchone():
            await message.reply("Вы уже зарегистрированы.")
        else:
            cur.execute("INSERT INTO users (user_id, password) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, password))
            conn.commit()
            await message.reply("Регистрация прошла успешно.")
    except Exception as e:
        logging.error(f"Ошибка при регистрации пользователя: {e}")
        await message.reply("Ошибка регистрации. Попробуйте позже.")
    finally:
        cur.close()
        conn.close()

# Удаление сообщений
@router.message(Command("delete"))
async def delete_messages(message: Message):
    user_id = message.from_user.id

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем, зарегистрирован ли пользователь
        cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
        if cur.fetchone():
            if message.reply_to_message:
                try:
                    await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
                    await bot.delete_message(message.chat.id, message.message_id)
                except Exception as e:
                    logging.error(f"Ошибка удаления сообщения: {e}")
                    await message.reply("Не удалось удалить сообщение.")
            else:
                await message.reply("Команда должна быть ответом на сообщение, которое вы хотите удалить.")
        else:
            await message.reply("Вы не зарегистрированы.")
    except Exception as e:
        logging.error(f"Ошибка при выполнении команды /delete: {e}")
        await message.reply("Ошибка при выполнении команды.")
    finally:
        cur.close()
        conn.close()

# Сохранение всех сообщений
async def save_message(chat_id, user_id, text):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO messages (chat_id, user_id, message) VALUES (%s, %s, %s)", (chat_id, user_id, text))
        conn.commit()
    except Exception as e:
        logging.error(f"Ошибка сохранения сообщения: {e}")
    finally:
        cur.close()
        conn.close()

@router.message(Command("summarise"))
async def delete_messages(message: Message):
    await message.reply("Ну ты кек")

# Логирование всех сообщений
@router.message()
async def log_message(message: Message):
    await save_message(message.chat.id, message.from_user.id, message.text)


# Команда /Подскажи
@router.message(Command("help"))
async def start_question(message: Message, state: FSMContext):
    await message.reply("С чем вам помочь? Пожалуйста, отправьте свой вопрос.")
    # Устанавливаем состояние ожидания вопроса
    await state.set_state(QuestionStates.waiting_for_question)
    await state.update_data(chat_id=message.chat.id, user_id=message.from_user.id)
    await message.reply("С чем вам помочь? Пожалуйста, отправьте свой вопрос.")

# Обработка следующего сообщения пользователя
@router.message(QuestionStates.waiting_for_question)
async def handle_question_response(message: Message, state: FSMContext):
    # Проверяем, что сообщение пришло от ожидаемого пользователя
    data = await state.get_data()
    if message.chat.id != data.get("chat_id") or message.from_user.id != data.get("user_id"):
        return  # Игнорируем сообщение, если оно не от того же пользователя

    question = message.text

    # Сбрасываем состояние, чтобы больше не ждать сообщений
    await state.clear()

    try:
        # Отправляем запрос в OpenAI
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=question,
            temperature=0.7,
            max_tokens=200,
        )
        answer = response.choices[0].text.strip()
        await message.reply(f"Вот что я думаю:\n\n{answer}")
    except Exception as e:
        logging.error(f"Ошибка при обращении к OpenAI: {e}")
        await message.reply("Не удалось получить ответ. Попробуйте позже.")


# Установка команд бота
async def set_bot_commands():
    commands = [
        BotCommand(command="register", description="Зарегистрироваться"),
        BotCommand(command="delete", description="Удалить сообщение"),
        BotCommand(command="summarise", description="А что в итоге?"),
        BotCommand(command="help", description="А, я, с чем помочь?")
    ]
    await bot.set_my_commands(commands)

# Основной запуск
async def main():
    await set_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
