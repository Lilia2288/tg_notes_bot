import json
import asyncio
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram import F
from config import TOKEN

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db_file = Path("db.json")

class NoteForm(StatesGroup):
    title = State()
    description = State()
    remind_at = State()

def read_db():
    if not db_file.exists():
        return {}
    with db_file.open("r", encoding="utf-8") as f:
        return json.load(f)
    
def write_db(data):
    with db_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/new"), KeyboardButton(text="/notes")]
    ],
    resize_keyboard=True
)

class NoteForm(StatesGroup):
    title = State()
    description = State()
    remind_at = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привіт! Щоб створити нотатку, натисни /new\nЩоб переглянути нотатки — /notes",
        reply_markup=main_keyboard
    )

@dp.message(Command("new"))
async def cmd_new(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("введи назву нотатки")
    await state.set_state(NoteForm.title)

@dp.message(F.state == NoteForm.title)
async def note_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("введіть опис нотатки")
    await state.set_state(NoteForm.description)
    
@dp.message(F.state == NoteForm.description)
async def cmd_description(message:types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "Введи дату та час нагадування у форматі: YYYY-MM-DD HH:MM (наприклад: 2025-03-29 17:30):"
        )
    await state.set_state(NoteForm.remind_at)

@dp.message(F.state == NoteForm.remind_at)
async def note_time(message: types.Message, state: FSMContext):
    try:
        remind_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("Невірний формат! Спробуй ще раз: YYYY-MM-DD HH:MM")
        return 
    data = await state.get_data()
    user_id = str(message.from_user.id)
    db = read_db()
    db.setdefault(user_id, []).append({
        "title": data["title"],
        "description": data["description"],
        "remind_at": remind_time.strftime("%Y-%m-%d %H:%M"),
        "notified": False
    })
    write_db(db)
    await message.answer("Нотатку збережено ✅")
    await state.clear()

@dp.message(Command("notes"))
async def cmd_notes(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    db = read_db()
    notes = db.get(user_id, [])
    if not notes:
        await message.answer("У тебе ще немає нотаток.")
        return
    text =  "\n\n".join(
        f"📌 <b>{n['title']}</b>\n📝 {n['description']}\n⏰ {n['remind_at']}"
        for n in notes
    )
    await message.answer()
async def reminder_worker():
    while True:
        db = read_db()
        changed = False
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for user_id, notes in db.item():
            for note in notes:
                if not note["notified"] and note["remind_at"] == now:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"🔔 Нагадування: <b>{note['title']}</b>\n{note['description']}"
                    )
                    note["notidied"] = True 
                    changed = True
        if changed:
            write_db(db)
        await asyncio.sleep()
async def on_startup(dispatcher: Dispatcher, bot: Bot):
    asyncio.create_task(reminder_worker())
if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot, on_startup=on_startup))