import logging
import asyncio
import random
import os
from qs import *
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

TOKEN = "....."

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

active_victorina = False #Активна ли викторинна
correct_answers = 0  # Количество правильних ответов

#Добавим словарь, где будет храниться состояние викторины
user_game_data = {}

# Создаем папку "user", если её нет
if not os.path.exists("user"):
    os.makedirs("user")

#старт
@dp.message(Command("start"))
async def start_handler(message: Message):
    global active_victorina
    user_id = message.from_user.id

    #Це означає: якщо вікторина існує, і ще не закінчена — не запускаємо нову
    if user_id in user_game_data and user_game_data[user_id]['current'] < len(user_game_data[user_id]['questions']):
        await message.answer("Ви вже почали вікторину.")
        return

    #Дізнаємося сразу він хоче дізнатися правильність відповіді чи в кінці вікторини
    answer_mode_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Дізнатися зараз", callback_data="mode_instant")],
            [InlineKeyboardButton(text="Дізнатися потім", callback_data="mode_end")]
        ]
    )
    await message.answer("Ти хочеш дізнаватися відповідь зараз чи потім?:", reply_markup=answer_mode_keyboard)

    #Записувати інфу о користувачів в текстовий файл
    logging.info(f"\nПользователь:{message.from_user.full_name}\n Айди человека: {message.from_user.id} \n User имя человека: {message.from_user.username} \n Страна: {message.from_user.language_code} \n Есть ли премиум?: {message.from_user.is_premium}\n")  # Логируем событие
    active_victorina = True

    full_people_name = message.from_user.full_name
    id_name = message.from_user.id

    user_info = f"Пользователь:\n Айди человека: {message.from_user.id}\n Полное имя человека: {message.from_user.full_name} \n User имя человека: {message.from_user.username} \n Страна: {message.from_user.language_code} \n Есть ли премиум?: {message.from_user.is_premium}\n"

    file_path = f"user/{id_name}({full_people_name}).txt"
    
    # Записываем или дополняем файл информацией
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(user_info)

#Обработчик какой режим вибрав користувач
@dp.callback_query(lambda c: c.data.startswith("mode_"))
async def set_answer_mode(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    mode = callback_query.data.replace("mode_", "")

    # Удаляем старую клавиатуру (режим ответа)
    await callback_query.message.edit_reply_markup(reply_markup=None)

    user_game_data[user_id] = {
        "mode": mode,
        "questions": [],
        "current":0,
        "score":0,
        "answers": []  # Сюди зберігатимемо відповіді
    }

    #Кнопки з рівнями тяжості
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Легкая (20 стран)", callback_data="level_easy")],
            [InlineKeyboardButton(text="Средняя (50 стран)", callback_data="level_medium")],
            [InlineKeyboardButton(text="Сложная (70 стран)", callback_data="level_hard")],
            [InlineKeyboardButton(text="Суперсложная (100 стран)", callback_data="level_extreme")]
        ]
    )
    await callback_query.message.answer("Привет! Выбери уровень сложности:", reply_markup=keyboard)

#проверка какую сложность вибрал пользователь
@dp.callback_query(lambda c: c.data.startswith("level_"))
async def complexity(callback_query: CallbackQuery):
    global user_id
    user_id = callback_query.from_user.id

    # Удаляем старую клавиатуру (сложность)
    await callback_query.message.edit_reply_markup(reply_markup=None)

    if user_id not in user_game_data or user_game_data[user_id].get("mode") is None:
        await callback_query.answer("Спочатку вибери режим відповідей")
        return

    level_mapping = {
        "level_easy": "Ты выбрал лёгкий уровень!",
        "level_medium": "Ты выбрал средний уровень!",
        "level_hard": "Ты выбрал сложный уровень!",
        "level_extreme": "Ты выбрал суперсложный уровень!"
    }
    response_text = level_mapping.get(callback_query.data, "Неизвестный выбор.")

    #Пишеться пользователю в тг
    await callback_query.message.answer(response_text)
    await callback_query.answer()

    #Пишем в терминал какую сложность выбрал пользователь
    logging.info(f"Пользователь {callback_query.from_user.full_name} вибрал сложность: {level_mapping.get(callback_query.data)}")

    #кол. вопросов
    level_questions_count = {
        "level_easy": 20,
        "level_medium": 50,
        "level_hard": 70,
        "level_extreme": 120
    }
    count = level_questions_count.get(callback_query.data, 5)

    selected_keys = sample(list(questions.keys()), count)
    user_game_data[user_id]["questions"] = selected_keys
    user_game_data[user_id]["current"] = 0
    user_game_data[user_id]["score"] = 0

    await send_questions(callback_query.message, user_id)

#Отправка вопросов
async def send_questions(message: Message, user_id: int):
    data = user_game_data[user_id]
    if data['current'] >= len(data['questions']):
        await message.answer(f"Гра завершена! Ти набрав {data['score']} з {len(data['questions'])} балів.",)
        return
    
    key = data['questions'][data['current']]
    number_question = data['current'] + 1

    #Правильный ответ
    correct = questions[key]

    # Получаем 3 случайных Неправильных ответа (исключая правильный)
    all_answers = list(questions.values())
    all_answers.remove(correct)
    random_flags = [correct] + sample(all_answers, 3)
    random_flags_extreme = [correct] + sample(all_answers, 4)

    shuffle(random_flags)

    #для екстрима
    shuffle(random_flags_extreme)

    user_correct_answers[user_id] = correct
    data['current'] += 1

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=flag, callback_data=flag)] for flag in random_flags]
    )
    await message.answer(f"{number_question}) Який прапор країни: {key}?", reply_markup=keyboard)

#Логика на то правильно ли ответил пользователь
@dp.callback_query(lambda c: not c.data.startswith("level_") and not c.data.startswith("mode_"))
async def check_answer(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_answer = callback_query.data
    correct_answer = user_correct_answers.get(user_id)

    #Оцінка правильності відповіді — це треба зробити ДО запису
    is_correct = user_answer == correct_answer

    #Запис результату в answers
    user_game_data[user_id]["answers"].append({
        "question": correct_answer,
        "user_answer": user_answer,
        "is_correct": is_correct
    })
    
    #Спроба прибрати клавіатуру
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.warning(f"Не удалось удалить клавиатуру: {e}")

    #Перевірка відповіді
    if is_correct:
        user_game_data[user_id]['score'] += 1
        print(f"Вірна відповідь\n")

    #Перевірка на те що чи хоче бачити користувач зразу відповідь чи аж в кінці
    mode = user_game_data[user_id].get("mode", "end")
    if mode == "instant":
        if is_correct:
            await callback_query.answer("Правильно!")
            print("Вірна відповідь!\n")
        else:
            await callback_query.answer("Ти помилився!")
            print("Не вірна відповідь!\n")

    #Продовження перевірки відповіді
    else:
        await callback_query.answer("Відповідь ти дізнаєшся в кінці...")

    await send_questions(callback_query.message, user_id)



#Стоп
@dp.message(Command("stop"))
async def stop_handler(message: Message):
    global active_victorina
    user_id = message.from_user.id

    #якщо він ще раз захоче вимкнути вікторину
    if user_id not in user_game_data:
        await message.answer("У тебе немає активної вікторини.")
        return
    
    #Словник з даними гри конкретного користувача
    data = user_game_data[user_id]

    #Позначаємо, що гра закінчена (щоб команда /incorrect працювала)
    data["current"] = len(data["questions"])

    answers_count = len(data["answers"])

    #Скільки всього питань було заплановано
    total = len(data["questions"])

    #На якому питанні зараз користувач
    current = data["current"]

    #Скільки правильних відповідей він вже дав
    score = data["score"]

    #Пишеться пользователю в тг
    await message.answer(f"Гру зупинено \nТи відповів(ла) на {answers_count} з {total} питань.\nПравильні: {score} країн(и).")
    await message.answer("Навіщо ти мене зупини??? :(")

    #Пишеться в терминал
    logging.info(f"{message.from_user.full_name}решыл остановить бота.")
    active_victorina = False



#Команда incorrect
@dp.message(Command("incorrect"))
async def incorrect_handler(message: Message):
    user_id = message.from_user.id

    if user_id not in user_game_data:
        await message.answer("У тебе немає жодної завершеної або зупиненої вікторини.")
        return

    data = user_game_data[user_id]

    if data["current"] < len(data["questions"]):
        await message.answer("Вікторина ще не завершена. Спочатку закінчи або зупини гру.")
        return

    if not data.get("answers"):
        await message.answer("Немає даних про твої відповіді.")
        return

    summary = ""

    for idx, ans in enumerate(data["answers"], 1):
        correct_answer = ans["question"]
        user_answer = ans["user_answer"]
        is_correct = ans["is_correct"]
        result_icon = "✅" if is_correct else "❌"

        summary += (
            f"{idx}) Який прапор країни: {correct_answer}\n"
            f"Твоя відповідь: {user_answer} {result_icon}\n"
            f"Правильна відповідь: {correct_answer}\n\n"
        )

    max_len = 4000
    for i in range(0, len(summary), max_len):
        await message.answer(summary[i:i+max_len])



# Основная функція для запуска бота
async def main():
    # Запуск обработки собитий
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())  # Запуск основного цикла собитий