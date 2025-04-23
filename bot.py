import json
import asyncio
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import TOKEN

# ──────────────────────── 1. Ініціалізація ────────────────────────
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ───────────────────────── 2. “База даних” ─────────────────────────
db_file = Path("db.json")


def read_db() -> dict:
    if not db_file.exists():
        return {}
    with db_file.open(encoding="utf-8") as f:
        return json.load(f)


def write_db(data: dict) -> None:
    with db_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ───────────────────────── 3. Клавіатури ──────────────────────────
builder = ReplyKeyboardBuilder()
builder.button(text="/new")
builder.button(text="/notes")
builder.adjust(2)                      # 2 кнопки в ряд
main_keyboard = builder.as_markup(resize_keyboard=True)

# ───────────────────────── 4. FSM-форма ───────────────────────────
class NoteForm(StatesGroup):
    title = State()
    description = State()
    remind_at = State()


# ───────────────────────── 5. Хендлери ────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привіт!\n/new – створити нотатку\n/notes – показати усі нотатки",
        reply_markup=main_keyboard,
    )


@dp.message(Command("new"))
async def cmd_new(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Введи назву нотатки:")
    await state.set_state(NoteForm.title)


@dp.message(StateFilter(NoteForm.title))
async def note_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введи опис нотатки:")
    await state.set_state(NoteForm.description)


@dp.message(StateFilter(NoteForm.description))
async def note_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "Введи дату та час у форматі YYYY-MM-DD HH:MM (наприклад 2025-03-29 17:30):"
    )
    await state.set_state(NoteForm.remind_at)


@dp.message(StateFilter(NoteForm.remind_at))
async def note_time(message: types.Message, state: FSMContext):
    try:
        remind_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("Невірний формат. Спробуй ще раз: YYYY-MM-DD HH:MM")
        return

    data = await state.get_data()
    user_id = str(message.from_user.id)
    db = read_db()
    db.setdefault(user_id, []).append(
        {
            "title": data["title"],
            "description": data["description"],
            "remind_at": remind_time.strftime("%Y-%m-%d %H:%M"),
            "notified": False,
        }
    )
    write_db(db)

    await message.answer("Нотатку збережено ✅")
    await state.clear()


@dp.message(Command("notes"))
async def cmd_notes(message: types.Message):
    user_id = str(message.from_user.id)
    notes = read_db().get(user_id, [])

    if not notes:
        await message.answer("У тебе ще немає нотаток.")
        return

    text = "\n\n".join(
        f"📌 <b>{n['title']}</b>\n📝 {n['description']}\n⏰ {n['remind_at']}"
        for n in notes
    )
    await message.answer(text)


# ─────────────── 6. Фоновий воркер-нагадувач ──────────────────────
async def reminder_worker() -> None:
    while True:
        db = read_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        changed = False

        for user_id, notes in db.items():
            for note in notes:
                if not note["notified"] and note["remind_at"] == now:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"🔔 Нагадування: <b>{note['title']}</b>\n{note['description']}",
                    )
                    note["notified"] = True
                    changed = True

        if changed:
            write_db(db)

        await asyncio.sleep(60)


async def on_startup(dispatcher: Dispatcher) -> None:
    asyncio.create_task(reminder_worker())


# ────────────────────────── 7. Запуск ─────────────────────────────
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot, on_startup=on_startup))
