from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

router = Router()
#SFM состояния для корзины, воронки регистрации, и оплаты заказа
class RegisterState(StatesGroup):
    waiting_for_phone = State()


class CartState(StatesGroup):
    managing_cart = State()


class OrderState(StatesGroup):
    waiting_for_address = State()