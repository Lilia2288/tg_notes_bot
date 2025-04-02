import json
import asyncio
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import TOKEN

bot = Bot(token=TOKEN, parse_mode="HTML")
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