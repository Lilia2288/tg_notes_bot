import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())

DB_FILE = Path("db.json")
# ─────────────────────── 1. Логи ────────────────────────

def read_db() -> dict:
    if not DB_FILE.exists():
# ─────────────────────── 2. Бот, dp ─────────────────────
        return {}
    with DB_FILE.open(encoding="utf-8") as f:
        return json.load(f)

def write_db(data: dict) -> None:
    with DB_FILE.open("w", encoding="utf-8") as f:
# ─────────────────────── 3. “База даних” ────────────────
        json.dump(data, f, indent=2, ensure_ascii=False)


kb = ReplyKeyboardBuilder()
kb.button(text="/new")
kb.button(text="/notes")
kb.adjust(2)
MAIN_KB = kb.as_markup(resize_keyboard=True)


class NoteForm(StatesGroup):
    title = State()
    description = State()
    remind_at = State()

# ─────────────────────── 4. Клавіатура ──────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привіт!\n/new – створити нотатку\n/notes – показати усі нотатки",
# ─────────────────────── 5. FSM ────────────────────────
        reply_markup=MAIN_KB,
    )

@dp.message(Command("new"))
async def cmd_new(message: types.Message, state: FSMContext):

# ─────────────────────── 6. Хендлери ───────────────────
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

        "Введи дату й час у форматі YYYY-MM-DD HH:MM "
        "(наприклад 2025-03-29 17:30):"
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


# ─────────────────────── 7. Воркер-нагадувач ───────────
try:
    from zoneinfo import ZoneInfo

    KYIV_TZ = ZoneInfo("Europe/Kyiv")
except Exception:
    KYIV_TZ = None
    logger.warning("tzdata не знайдено — використовую системний час.")

async def reminder_worker() -> None:
    while True:
        now_dt = datetime.now(KYIV_TZ) if KYIV_TZ else datetime.now()
        now = now_dt.strftime("%Y-%m-%d %H:%M")

        db = read_db()
        changed = False

        for user_id, notes in db.items():
            for note in notes:
                if not note["notified"] and note["remind_at"] == now:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔔 Нагадування: <b>{note['title']}</b>\n{note['description']}",
                    )
                    note["notified"] = True
                    changed = True

        if changed:
            write_db(db)

        await asyncio.sleep(60)  # раз на хвилину


# ─────────────────────── 8. Стартовий хук ─────────────────
@dp.startup()
async def _startup() -> None:  # <-­ без аргументів
    asyncio.create_task(reminder_worker())
    logger.info("Reminder worker запущено")


# ─────────────────────── 9. Запуск ───────────────────────
async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
