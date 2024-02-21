import aiohttp
import asyncio
import random

from googletrans import Translator

from datetime import datetime


from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.utils.formatting import (
   Bold, as_list, as_marked_section
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router, types


router = Router()
list_of_possible_meals=[]
translator = Translator()

class number_of_recipes(StatesGroup):
   waiting_for_number = State()
   waiting_for_show = State()

@router.message(Command("category_search_random"))
async def category_search_random(message: Message, command: CommandObject,
                                 state: FSMContext):
    global list_of_possible_meals
    if command.args is None or command.args.isalpha() :
        await message.answer(
            "Ошибка: не переданы аргументы. Попробуйте"
            " /category_search_random 3"
        )
    await state.set_data({'number_of_recipes': int(command.args)})

    builder = ReplyKeyboardBuilder()
    async with aiohttp.ClientSession() as session:
        async with session.get(url='http://www.themealdb.com/api/json/v1/1/list.php?c=list') as resp:
            resp_text = await resp.json()
            for some in resp_text['meals']:
                builder.add(types.KeyboardButton(text=some['strCategory']))
                list_of_possible_meals.append(some['strCategory'])
            builder.adjust(5)
    await message.answer(
        f"Выберите категорию:",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )
    await state.set_state(number_of_recipes.waiting_for_number.state)

@router.message(number_of_recipes.waiting_for_number)
async def meals(message: types.Message, state: FSMContext):
    global list_of_possible_meals
    meals = await state.get_data()
    if message.text in list_of_possible_meals:
        #Попросили рецепт по кнопке
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"http://www.themealdb.com/api/json/v1/1/filter.php?c={message.text}") as resp:
                data = await resp.json()
        dict_of_meals={}
        for a in range(len(data['meals'])):
            dict_of_meals[data['meals'][a]['strMeal']] = data['meals'][a]["idMeal"]
        ru_dict_of_meals={}
        for key, value in dict_of_meals.items():
            translated_key = translator.translate(key, dest='ru').text
            ru_dict_of_meals[translated_key] = value
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Покажи рецепты")],],
            resize_keyboard=True,
        )
        if meals['number_of_recipes'] > len(dict_of_meals):
            #попросили рецептов больше чем есть
            await message.answer(f"Найдено только {len(dict_of_meals)} "
                                 f"блюд(а) в категории {message.text}: "
                                 f"{', '.join(ru_dict_of_meals.keys())}", reply_markup=keyboard)
            await state.set_data({'id_of_recepts': ru_dict_of_meals})
        else:
            list_of_keys = list(ru_dict_of_meals.keys())
            rand_keys = list(random.sample(list_of_keys, k=int(meals['number_of_recipes'])))
            rand_dict_of_meals={key: ru_dict_of_meals[key] for key in rand_keys}
            await message.answer(f"Найдено {meals['number_of_recipes']} случайных "
                                 f"блюд(а) в категории {message.text}: "
                                 f"{', '.join(rand_dict_of_meals.keys())}", reply_markup=keyboard)
            await state.set_data({'id_of_recepts' : rand_dict_of_meals})
        await state.set_state(number_of_recipes.waiting_for_show.state)
    else:
        #Попросили рецепт не по кнопке, написав не существующую категорию.
        await message.answer('Нет указанной категории! Используйте кнопку диалога или введите новую команду')

@router.message(number_of_recipes.waiting_for_show)
async def recipe_id(message: types.Message, state: FSMContext):
    if message.text == 'Покажи рецепты':
        mystate = await state.get_data()
        for meal, id in mystate['id_of_recepts'].items():
            async with aiohttp.ClientSession() as session:
                async with session.get(url=f"http://www.themealdb.com/api/json/v1/1/lookup.php?i={int(id)}") as resp:
                    data = await resp.json()
            ingridients = {}
            for a in range(1, 21):
                if data['meals'][0][f'strIngredient{a}'] is None:
                    next
                elif data['meals'][0][f'strIngredient{a}'] == "":
                    next
                else:
                    ingridients[data['meals'][0][f'strIngredient{a}']] = data['meals'][0][f'strMeasure{a}']
            str_ingridients = '\n '.join([f'{key}: {value}' for key, value in ingridients.items()])
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="/start")],
                          [types.KeyboardButton(text="/category_search_random 3")]],
                resize_keyboard=True,
            )
            bot_msg = (f"{meal}\n\n"
                       f"{translator.translate(data['meals'][0]['strInstructions'], dest='ru').text}"
                       f"\n\n Ингридиенты:\n {translator.translate(str_ingridients, dest='ru').text}")
            if len(bot_msg) > 4096:
                #если сообщение длиннее допустимого для отправки(Miscellaneous Оссобуко..)
                bot_msgs = [bot_msg[i:i + 4096] for i in range(0, len(bot_msg), 4096)]
                for part_msg in bot_msgs:
                    await message.answer(part_msg, reply_markup=keyboard)
            else:
                await message.answer(bot_msg, reply_markup=keyboard)
    else:
        await message.answer(f'Используйте кнопку диалога или введите новую команду')

@router.message()
async def commands(message: types.Message):
    response = as_list(
        as_marked_section(
            Bold("Команды:"),
            "/category_search_random (ваше число)- выбор категории блюда и числа рецептов\n"
            "/start - начало работы",
            marker="✅ ",
        ),
    )
    await message.answer(
        **response.as_kwargs()
    )