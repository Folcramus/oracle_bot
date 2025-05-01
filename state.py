from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

# Ваши импорты:
# from models import User, async_session
# from bitrix24 import bitrix24
# from catalog import catalog

router = Router()

class RegisterState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_address = State()