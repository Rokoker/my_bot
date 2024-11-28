from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем хранилище состояний
dp = Dispatcher(storage=MemoryStorage())

# Определяем группу состояний
class QuestionStates(StatesGroup):
    waiting_for_question = State()

# Команда /Подскажи
@router.message(Command("Подскажи"))
async def start_question(message: Message, state: FSMContext):
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
