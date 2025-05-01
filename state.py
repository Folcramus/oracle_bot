from aiogram import  Router
from aiogram.fsm.state import State, StatesGroup


router = Router()
#SFM состояния для корзины, воронки регистрации, и оплаты заказа
class RegisterState(StatesGroup):
    waiting_for_phone = State()


class CartState(StatesGroup):
    managing_cart = State()


class OrderState(StatesGroup):
    waiting_for_address = State()