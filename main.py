import asyncio
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramConflictError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SHOP_BOT_TOKEN = os.getenv("SHOP_BOT_TOKEN", "")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://example.com").rstrip("/")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

shop_bot = Bot(SHOP_BOT_TOKEN) if SHOP_BOT_TOKEN else None
admin_bot = Bot(ADMIN_BOT_TOKEN) if ADMIN_BOT_TOKEN else None
shop_dp = Dispatcher()
admin_dp = Dispatcher()
shop_router = Router()
admin_router = Router()
shop_dp.include_router(shop_router)
admin_dp.include_router(admin_router)

CATEGORIES = {
    "Крупная бытовая техника": ["Холодильник", "Стиральная машина", "Плита", "Духовка", "Посудомойка"],
    "Мелкая бытовая техника": ["Чайник", "Тостер", "Микроволновка", "Блендер", "Миксер", "Кофеварка"],
    "Климатическая техника": ["Кондиционер", "Обогреватель", "Вентилятор", "Увлажнитель", "Очиститель воздуха"],
    "Техника для уборки": ["Пылесос", "Робот-пылесос", "Пароочиститель", "Мойка высокого давления"],
    "Кухонная техника": ["Мультиварка", "Аэрогриль", "Кухонный комбайн", "Кофемашина", "Мясорубка"],
    "Техника для ухода за одеждой": ["Утюг", "Отпариватель", "Сушильная машина"],
    "Техника для красоты и ухода": ["Фен", "Стайлер", "Электробритва", "Машинка для стрижки"],
    "Техника для развлечений": ["Телевизор", "Игровая приставка", "Проектор", "Аудиосистема"],
    "Умная техника": ["Умные лампы", "Колонки", "Розетки", "Камеры", "Роботы"],
    "Встраиваемая техника": ["Встроенный холодильник", "Встроенная духовка", "Варочная панель", "Вытяжка", "Встроенная посудомойка"],
    "Техника для воды": ["Водонагреватель", "Фильтр для воды", "Кулер", "Насос"],
    "Техника для безопасности": ["Видеодомофон", "Камеры видеонаблюдения", "Сигнализация", "Датчики"],
}

CATEGORY_TRANSLATIONS = {
    "Крупная бытовая техника": {"ru": "Крупная бытовая техника", "uz": "Katta maishiy texnika", "en": "Large appliances"},
    "Мелкая бытовая техника": {"ru": "Мелкая бытовая техника", "uz": "Kichik maishiy texnika", "en": "Small appliances"},
    "Климатическая техника": {"ru": "Климатическая техника", "uz": "Iqlim texnikasi", "en": "Climate appliances"},
    "Техника для уборки": {"ru": "Техника для уборки", "uz": "Tozalash texnikasi", "en": "Cleaning appliances"},
    "Кухонная техника": {"ru": "Кухонная техника", "uz": "Oshxona texnikasi", "en": "Kitchen appliances"},
    "Техника для ухода за одеждой": {"ru": "Техника для ухода за одеждой", "uz": "Kiyim parvarishi texnikasi", "en": "Clothing care"},
    "Техника для красоты и ухода": {"ru": "Техника для красоты и ухода", "uz": "Go'zallik va parvarish texnikasi", "en": "Beauty & care"},
    "Техника для развлечений": {"ru": "Техника для развлечений", "uz": "Ko'ngilochar texnika", "en": "Entertainment"},
    "Умная техника": {"ru": "Умная техника", "uz": "Aqlli texnika", "en": "Smart technology"},
    "Встраиваемая техника": {"ru": "Встраиваемая техника", "uz": "O'rnatiladigan texnika", "en": "Built-in appliances"},
    "Техника для воды": {"ru": "Техника для воды", "uz": "Suv texnikasi", "en": "Water appliances"},
    "Техника для безопасности": {"ru": "Техника для безопасности", "uz": "Xavfsizlik texnikasi", "en": "Security technology"},
}

SUBCATEGORY_TRANSLATIONS = {
    "Холодильник": {"ru": "Холодильник", "uz": "Muzlatgich", "en": "Refrigerator"},
    "Стиральная машина": {"ru": "Стиральная машина", "uz": "Kir yuvish mashinasi", "en": "Washing machine"},
    "Плита": {"ru": "Плита", "uz": "Plita", "en": "Cooker"},
    "Духовка": {"ru": "Духовка", "uz": "Duxovka", "en": "Oven"},
    "Посудомойка": {"ru": "Посудомойка", "uz": "Idish yuvish mashinasi", "en": "Dishwasher"},
    "Чайник": {"ru": "Чайник", "uz": "Choynak", "en": "Kettle"},
    "Тостер": {"ru": "Тостер", "uz": "Toster", "en": "Toaster"},
    "Микроволновка": {"ru": "Микроволновка", "uz": "Mikroto'lqinli pech", "en": "Microwave"},
    "Блендер": {"ru": "Блендер", "uz": "Blender", "en": "Blender"},
    "Миксер": {"ru": "Миксер", "uz": "Mikser", "en": "Mixer"},
    "Кофеварка": {"ru": "Кофеварка", "uz": "Qahva qaynatgich", "en": "Coffee maker"},
    "Кондиционер": {"ru": "Кондиционер", "uz": "Konditsioner", "en": "Air conditioner"},
    "Обогреватель": {"ru": "Обогреватель", "uz": "Isitgich", "en": "Heater"},
    "Вентилятор": {"ru": "Вентилятор", "uz": "Ventilyator", "en": "Fan"},
    "Увлажнитель": {"ru": "Увлажнитель", "uz": "Namlagich", "en": "Humidifier"},
    "Очиститель воздуха": {"ru": "Очиститель воздуха", "uz": "Havo tozalagich", "en": "Air purifier"},
    "Пылесос": {"ru": "Пылесос", "uz": "Changyutgich", "en": "Vacuum cleaner"},
    "Робот-пылесос": {"ru": "Робот-пылесос", "uz": "Robot changyutgich", "en": "Robot vacuum"},
    "Пароочиститель": {"ru": "Пароочиститель", "uz": "Bug'li tozalagich", "en": "Steam cleaner"},
    "Мойка высокого давления": {"ru": "Мойка высокого давления", "uz": "Yuqori bosimli yuvish moslamasi", "en": "Pressure washer"},
    "Мультиварка": {"ru": "Мультиварка", "uz": "Multivarka", "en": "Multicooker"},
    "Аэрогриль": {"ru": "Аэрогриль", "uz": "Aerogril", "en": "Air fryer"},
    "Кухонный комбайн": {"ru": "Кухонный комбайн", "uz": "Oshxona kombayni", "en": "Food processor"},
    "Кофемашина": {"ru": "Кофемашина", "uz": "Kofe mashinasi", "en": "Coffee machine"},
    "Мясорубка": {"ru": "Мясорубка", "uz": "Go'sht maydalagich", "en": "Meat grinder"},
    "Утюг": {"ru": "Утюг", "uz": "Dazmol", "en": "Iron"},
    "Отпариватель": {"ru": "Отпариватель", "uz": "Bug'lagich", "en": "Garment steamer"},
    "Сушильная машина": {"ru": "Сушильная машина", "uz": "Quritish mashinasi", "en": "Dryer"},
    "Фен": {"ru": "Фен", "uz": "Fen", "en": "Hair dryer"},
    "Стайлер": {"ru": "Стайлер", "uz": "Stayler", "en": "Styler"},
    "Электробритва": {"ru": "Электробритва", "uz": "Elektr ustara", "en": "Electric shaver"},
    "Машинка для стрижки": {"ru": "Машинка для стрижки", "uz": "Soch olish mashinasi", "en": "Hair clipper"},
    "Телевизор": {"ru": "Телевизор", "uz": "Televizor", "en": "Television"},
    "Игровая приставка": {"ru": "Игровая приставка", "uz": "O'yin konsoli", "en": "Game console"},
    "Проектор": {"ru": "Проектор", "uz": "Proyektor", "en": "Projector"},
    "Аудиосистема": {"ru": "Аудиосистема", "uz": "Audio tizim", "en": "Audio system"},
    "Умные лампы": {"ru": "Умные лампы", "uz": "Aqlli lampalar", "en": "Smart lights"},
    "Колонки": {"ru": "Колонки", "uz": "Aqlli karnaylar", "en": "Speakers"},
    "Розетки": {"ru": "Розетки", "uz": "Aqlli rozetkalar", "en": "Smart plugs"},
    "Камеры": {"ru": "Камеры", "uz": "Kameralar", "en": "Cameras"},
    "Роботы": {"ru": "Роботы", "uz": "Robotlar", "en": "Robots"},
    "Встроенный холодильник": {"ru": "Встроенный холодильник", "uz": "O'rnatiladigan muzlatgich", "en": "Built-in refrigerator"},
    "Встроенная духовка": {"ru": "Встроенная духовка", "uz": "O'rnatiladigan duxovka", "en": "Built-in oven"},
    "Варочная панель": {"ru": "Варочная панель", "uz": "Pishirish paneli", "en": "Cooktop"},
    "Вытяжка": {"ru": "Вытяжка", "uz": "Havo so'rgich", "en": "Cooker hood"},
    "Встроенная посудомойка": {"ru": "Встроенная посудомойка", "uz": "O'rnatiladigan idish yuvish mashinasi", "en": "Built-in dishwasher"},
    "Водонагреватель": {"ru": "Водонагреватель", "uz": "Suv isitgich", "en": "Water heater"},
    "Фильтр для воды": {"ru": "Фильтр для воды", "uz": "Suv filtri", "en": "Water filter"},
    "Кулер": {"ru": "Кулер", "uz": "Kuler", "en": "Water cooler"},
    "Насос": {"ru": "Насос", "uz": "Nasos", "en": "Pump"},
    "Видеодомофон": {"ru": "Видеодомофон", "uz": "Video domofon", "en": "Video intercom"},
    "Камеры видеонаблюдения": {"ru": "Камеры видеонаблюдения", "uz": "Kuzatuv kameralari", "en": "CCTV cameras"},
    "Сигнализация": {"ru": "Сигнализация", "uz": "Signalizatsiya", "en": "Alarm system"},
    "Датчики": {"ru": "Датчики", "uz": "Datchiklar", "en": "Sensors"},
}

SEED_PRODUCTS = [
    ("LG DoorCooling+ GC-B509PQAM", "Холодильник", 7499000, 8299000, "Холодильник LG с технологией DoorCooling+, No Frost, класс A++, объем 384 л", "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?auto=format&fit=crop&w=1000&q=85", 1),
    ("Samsung WW70T4020CX", "Стиральная машина", 4999000, 5599000, "Стиральная машина Samsung, загрузка 7 кг, EcoBubble, 1200 об/мин", "https://images.unsplash.com/photo-1626806787461-102c1bfaaea1?auto=format&fit=crop&w=1000&q=85", 1),
    ("Artel ART-12HG", "Кондиционер", 3999000, 4499000, "Кондиционер Artel 12 BTU, инверторный, режимы охлаждения и обогрева", "https://images.unsplash.com/photo-1631545806609-3b5d7f7d1e45?auto=format&fit=crop&w=1000&q=85", 1),
    ("Xiaomi Robot Vacuum S10", "Робот-пылесос", 2799000, 3199000, "Робот-пылесос Xiaomi, лазерная навигация LDS, влажная уборка", "https://images.unsplash.com/photo-1581579186983-6e7d1f1b9c45?auto=format&fit=crop&w=1000&q=85", 1),
    ("DeLonghi Magnifica S", "Кофемашина", 6499000, 7199000, "Автоматическая кофемашина DeLonghi, встроенная кофемолка, 1450 Вт", "https://images.unsplash.com/photo-1517256064527-09c73fc73e38?auto=format&fit=crop&w=1000&q=85", 1),
    ("DHL-2000M-TV120M", "Обогреватель", 1299000, 1499000, "Электрокамин-обогреватель 2000 Вт, термостат, эффект живого пламени", "https://images.unsplash.com/photo-1541018962155-1f8f7c6b9d6e?auto=format&fit=crop&w=1000&q=85", 0),
    ("Bosch MSM6M3", "Блендер", 899000, 999000, "Погружной блендер Bosch, мощность 1200 Вт, металлическая ножка", "https://images.unsplash.com/photo-1585515320310-259814833e62?auto=format&fit=crop&w=1000&q=85", 0),
    ("Samsung RB34T600", "Холодильник", 6199000, 0, "Холодильник Samsung No Frost, цифровой инвертор, объем 344 л", "https://images.unsplash.com/photo-1584568694244-14fbdf83bd30?auto=format&fit=crop&w=1000&q=85", 0),
]

DEFAULT_SETTINGS = {
    "shop_name": "Mediapark Home",
    "phone": "+998 71 203 33 33",
    "banner_title_ru": "Техника для дома. Всё нужное — в одном месте.",
    "banner_title_uz": "Uy uchun texnika. Kerakli hammasi — bir joyda.",
    "banner_title_en": "Home appliances. Everything you need in one place.",
    "maintenance": "false",
}

class OrderItem(BaseModel):
    id: int
    name: str
    price: int
    quantity: int = Field(ge=1)

class OrderPayload(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=5, max_length=30)
    address: str = Field(min_length=1, max_length=300)
    comment: str = Field(default="", max_length=1000)
    items: list[OrderItem] = Field(min_length=1)
    total: int = Field(ge=0)

class AddProductStates(StatesGroup):
    category = State()
    subcategory = State()
    name = State()
    price = State()
    old_price = State()
    specs = State()
    image = State()
    hit = State()

class PriceState(StatesGroup):
    product_id = State()
    value = State()

class SettingState(StatesGroup):
    key = State()
    value = State()

async def db_execute(query: str, params: tuple = (), fetch: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        if fetch:
            rows = await cur.fetchall()
            await db.commit()
            return [dict(r) for r in rows]
        await db.commit()
        return cur.lastrowid

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ru TEXT NOT NULL,
            name_uz TEXT NOT NULL,
            name_en TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            old_price INTEGER NOT NULL DEFAULT 0,
            specs_ru TEXT NOT NULL DEFAULT '',
            specs_uz TEXT NOT NULL DEFAULT '',
            specs_en TEXT NOT NULL DEFAULT '',
            image TEXT NOT NULL DEFAULT '',
            is_hit INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            comment TEXT NOT NULL DEFAULT '',
            items_json TEXT NOT NULL,
            total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        for key, value in DEFAULT_SETTINGS.items():
            await db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
        cur = await db.execute("SELECT COUNT(*) FROM products")
        count = (await cur.fetchone())[0]
        if count == 0:
            for name, category, price, old_price, specs, image, hit in SEED_PRODUCTS:
                await db.execute(
                    """INSERT INTO products
                    (name_ru,name_uz,name_en,category,price,old_price,specs_ru,specs_uz,specs_en,image,is_hit)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, name, name, category, price, old_price, specs, specs, specs, image, hit),
                )
        await db.commit()

async def get_settings():
    rows = await db_execute("SELECT key,value FROM settings", fetch=True)
    return {r["key"]: r["value"] for r in rows}

async def get_products():
    return await db_execute("SELECT * FROM products ORDER BY id DESC", fetch=True)

async def set_setting(key: str, value: str):
    await db_execute(
        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )

def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " сум"

def admin_only_message(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == ADMIN_ID)

def admin_only_callback(callback: CallbackQuery) -> bool:
    return bool(callback.from_user and callback.from_user.id == ADMIN_ID)

async def send_order_to_admin(order_id: int, payload: OrderPayload):
    if not admin_bot or not ADMIN_ID:
        return
    lines = [
        f"<b>🛒 Новый заказ №{order_id}</b>",
        f"<b>Клиент:</b> {payload.customer_name}",
        f"<b>Телефон:</b> {payload.phone}",
        f"<b>Адрес:</b> {payload.address}",
    ]
    if payload.comment:
        lines.append(f"<b>Комментарий:</b> {payload.comment}")
    lines.append("<b>Товары:</b>")
    for item in payload.items:
        lines.append(f"• {item.name} × {item.quantity} — {money(item.price * item.quantity)}")
    lines.append(f"<b>Итого: {money(payload.total)}</b>")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять в работу", callback_data=f"order:processing:{order_id}")],
        [InlineKeyboardButton(text="🚚 Доставлен", callback_data=f"order:completed:{order_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"order:cancelled:{order_id}")],
    ])
    try:
        await admin_bot.send_message(ADMIN_ID, "\n".join(lines), reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

@shop_router.message(CommandStart())
async def shop_start(message: Message):
    if not shop_bot:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Открыть каталог магазина", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="📞 Контакты и адрес", callback_data="shop:contacts")],
        [InlineKeyboardButton(text="🚚 Условия доставки", callback_data="shop:delivery")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="shop:orders")],
    ])
    try:
        await shop_bot.set_chat_menu_button(chat_id=message.chat.id, menu_button={"type": "web_app", "text": "🛒 Каталог", "web_app": {"url": WEBAPP_URL}})
    except Exception:
        pass
    await message.answer(
        "Добро пожаловать в Mediapark Home! 🏠\n\nБытовая техника для дома с быстрым оформлением заказа прямо в Telegram.",
        reply_markup=kb,
    )

@shop_router.callback_query(F.data == "shop:contacts")
async def shop_contacts(callback: CallbackQuery):
    settings = await get_settings()
    await callback.answer()
    await callback.message.answer(f"📞 {settings.get('phone', '')}\n🏠 Mediapark Home")

@shop_router.callback_query(F.data == "shop:delivery")
async def shop_delivery(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🚚 Доставка согласовывается менеджером после оформления заказа.")

@shop_router.callback_query(F.data == "shop:orders")
async def shop_orders(callback: CallbackQuery):
    await callback.answer()
    name = callback.from_user.first_name if callback.from_user else ""
    rows = await db_execute(
        "SELECT id,status,total,created_at FROM orders WHERE customer_name LIKE ? ORDER BY id DESC LIMIT 5",
        (f"%{name}%",),
        fetch=True,
    )
    if not rows:
        await callback.message.answer("📦 Заказов по вашему имени пока не найдено.")
        return
    text = "\n".join(f"№{r['id']} — {r['status']} — {money(r['total'])}" for r in rows)
    await callback.message.answer(f"📦 Последние заказы:\n{text}")

@admin_router.message(CommandStart())
async def admin_start(message: Message):
    if not admin_only_message(message):
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Панель управления магазином.", reply_markup=admin_menu())

@admin_router.message(F.text == "➕ Добавить товар")
async def admin_add_start(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    await state.set_state(AddProductStates.category)
    await message.answer("Выберите категорию:", reply_markup=category_keyboard())

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📦 Управление товарами")],
            [KeyboardButton(text="📋 Заказы"), KeyboardButton(text="⚙️ Настройки магазина")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🛠 Режим тех. работ")],
        ],
        resize_keyboard=True,
    )

def category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{i+1}. {name}", callback_data=f"cat:{name}")]
        for i, name in enumerate(CATEGORIES)
    ])

def subcategory_keyboard(category: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"sub:{name}")]
        for name in CATEGORIES[category]
    ])

@admin_router.callback_query(F.data.startswith("cat:"))
async def admin_category(callback: CallbackQuery, state: FSMContext):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    category = callback.data[4:]
    if category not in CATEGORIES:
        await callback.answer("Ошибка")
        return
    await state.update_data(category=category)
    await state.set_state(AddProductStates.subcategory)
    await callback.message.edit_text(f"Категория: {category}\nВыберите подкатегорию:", reply_markup=subcategory_keyboard(category))
    await callback.answer()

@admin_router.callback_query(F.data.startswith("sub:"))
async def admin_subcategory(callback: CallbackQuery, state: FSMContext):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    await state.update_data(subcategory=callback.data[4:])
    await state.set_state(AddProductStates.name)
    await callback.message.answer("Введите название товара:")
    await callback.answer()

@admin_router.message(AddProductStates.name)
async def admin_product_name(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductStates.price)
    await message.answer("Введите цену в сумах, только цифры:")

@admin_router.message(AddProductStates.price)
async def admin_product_price(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Цена должна содержать только цифры.")
        return
    await state.update_data(price=int(message.text.strip()))
    await state.set_state(AddProductStates.old_price)
    await message.answer("Введите старую цену или 0:")

@admin_router.message(AddProductStates.old_price)
async def admin_product_old_price(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Введите число.")
        return
    await state.update_data(old_price=int(message.text.strip()))
    await state.set_state(AddProductStates.specs)
    await message.answer("Введите характеристики товара. Можно несколькими строками:")

@admin_router.message(AddProductStates.specs)
async def admin_product_specs(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    await state.update_data(specs=message.text.strip())
    await state.set_state(AddProductStates.image)
    await message.answer("Отправьте фото товара прямо сюда или пришлите прямую HTTPS-ссылку на изображение:")

@admin_router.message(AddProductStates.image)
async def admin_product_image(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    image_url = ""
    if message.photo:
        photo = message.photo[-1]
        if not admin_bot:
            await message.answer("Бот не настроен.")
            return
        file = await admin_bot.get_file(photo.file_id)
        ext = Path(file.file_path or "").suffix.lower() or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        destination = UPLOAD_DIR / filename
        await admin_bot.download_file(file.file_path, destination)
        image_url = f"{WEBAPP_URL}/static/uploads/{filename}"
    elif message.text and re.match(r"^https?://", message.text.strip(), re.I):
        image_url = message.text.strip()
    else:
        await message.answer("Нужно отправить фото или прямую http/https-ссылку.")
        return
    await state.update_data(image=image_url)
    await state.set_state(AddProductStates.hit)
    await message.answer("Это хит продаж?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Да", callback_data="hit:1"), InlineKeyboardButton(text="Нет", callback_data="hit:0")]
    ]))

@admin_router.callback_query(F.data.startswith("hit:"))
async def admin_product_hit(callback: CallbackQuery, state: FSMContext):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    data = await state.get_data()
    hit = int(callback.data[4:])
    name = data["name"]
    category = data["subcategory"]
    price = int(data["price"])
    old_price = int(data["old_price"])
    specs = data["specs"]
    image = data["image"]
    await db_execute(
        """INSERT INTO products
        (name_ru,name_uz,name_en,category,price,old_price,specs_ru,specs_uz,specs_en,image,is_hit)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (name, name, name, category, price, old_price, specs, specs, specs, image, hit),
    )
    await state.clear()
    await callback.message.answer(f"✅ Товар «{name}» добавлен.", reply_markup=admin_menu())
    await callback.answer()

@admin_router.message(F.text == "📦 Управление товарами")
async def admin_products(message: Message):
    if not admin_only_message(message):
        return
    rows = await get_products()
    if not rows:
        await message.answer("Товаров нет.")
        return
    for p in rows:
        text = f"#{p['id']} {p['name_ru']}\n{money(p['price'])}\n🔥 Хит: {'Да' if p['is_hit'] else 'Нет'}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"price:{p['id']}")],
            [InlineKeyboardButton(text=f"🔥 {'Выкл' if p['is_hit'] else 'Вкл'} хит", callback_data=f"hit_toggle:{p['id']}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{p['id']}")],
        ])
        await message.answer(text, reply_markup=kb)

@admin_router.callback_query(F.data.startswith("price:"))
async def admin_price_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    pid = int(callback.data.split(":")[1])
    await state.update_data(product_id=pid)
    await state.set_state(PriceState.value)
    await callback.message.answer("Введите новую цену:")
    await callback.answer()

@admin_router.message(PriceState.value)
async def admin_price_save(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Только цифры.")
        return
    data = await state.get_data()
    await db_execute("UPDATE products SET price=? WHERE id=?", (int(message.text), int(data["product_id"])))
    await state.clear()
    await message.answer("✅ Цена изменена.", reply_markup=admin_menu())

@admin_router.callback_query(F.data.startswith("hit_toggle:"))
async def admin_hit_toggle(callback: CallbackQuery):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    pid = int(callback.data.split(":")[1])
    await db_execute("UPDATE products SET is_hit=CASE is_hit WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (pid,))
    await callback.answer("Готово")
    await callback.message.edit_reply_markup(reply_markup=None)

@admin_router.callback_query(F.data.startswith("delete:"))
async def admin_delete(callback: CallbackQuery):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    pid = int(callback.data.split(":")[1])
    await db_execute("DELETE FROM products WHERE id=?", (pid,))
    await callback.message.edit_text("🗑 Товар удалён.")
    await callback.answer()

@admin_router.message(F.text == "📋 Заказы")
async def admin_orders(message: Message):
    if not admin_only_message(message):
        return
    rows = await db_execute("SELECT * FROM orders WHERE status IN ('new','processing') ORDER BY id DESC", fetch=True)
    if not rows:
        await message.answer("Активных заказов нет.")
        return
    for o in rows:
        items = json.loads(o["items_json"])
        items_text = "\n".join(f"• {x['name']} × {x['quantity']}" for x in items)
        text = f"<b>Заказ №{o['id']}</b>\nКлиент: {o['customer_name']}\nТелефон: {o['phone']}\nАдрес: {o['address']}\n{items_text}\n<b>Итого: {money(o['total'])}</b>\nСтатус: {o['status']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"order:processing:{o['id']}"),
             InlineKeyboardButton(text="🚚 Доставлен", callback_data=f"order:completed:{o['id']}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"order:cancelled:{o['id']}")],
        ])
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@admin_router.callback_query(F.data.startswith("order:"))
async def admin_order_status(callback: CallbackQuery):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    _, status, oid = callback.data.split(":")
    if status not in {"processing", "completed", "cancelled"}:
        await callback.answer("Недопустимый статус", show_alert=True)
        return
    await db_execute("UPDATE orders SET status=? WHERE id=?", (status, int(oid)))
    labels = {"processing": "Принят в работу", "completed": "Доставлен", "cancelled": "Отменён"}
    await callback.answer(labels[status])
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

@admin_router.message(F.text == "⚙️ Настройки магазина")
async def admin_settings(message: Message):
    if not admin_only_message(message):
        return
    settings = await get_settings()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏪 Название", callback_data="set:shop_name")],
        [InlineKeyboardButton(text="📞 Телефон", callback_data="set:phone")],
        [InlineKeyboardButton(text="🇷🇺 Баннер RU", callback_data="set:banner_title_ru")],
        [InlineKeyboardButton(text="🇺🇿 Баннер UZ", callback_data="set:banner_title_uz")],
        [InlineKeyboardButton(text="🇬🇧 Баннер EN", callback_data="set:banner_title_en")],
    ])
    await message.answer(
        f"Название: {settings.get('shop_name')}\nТелефон: {settings.get('phone')}",
        reply_markup=kb,
    )

@admin_router.callback_query(F.data.startswith("set:"))
async def admin_setting_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only_callback(callback):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    key = callback.data[4:]
    await state.update_data(key=key)
    await state.set_state(SettingState.value)
    await callback.message.answer("Введите новое значение:")
    await callback.answer()

@admin_router.message(SettingState.value)
async def admin_setting_save(message: Message, state: FSMContext):
    if not admin_only_message(message):
        return
    data = await state.get_data()
    await set_setting(data["key"], message.text.strip())
    await state.clear()
    await message.answer("✅ Настройка сохранена.", reply_markup=admin_menu())

@admin_router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if not admin_only_message(message):
        return
    products = await db_execute("SELECT COUNT(*) c FROM products", fetch=True)
    orders = await db_execute("SELECT COUNT(*) c FROM orders", fetch=True)
    completed = await db_execute("SELECT COALESCE(SUM(total),0) s FROM orders WHERE status='completed'", fetch=True)
    await message.answer(
        f"📊 Статистика\n\nТоваров: {products[0]['c']}\nЗаказов: {orders[0]['c']}\nВыполнено на сумму: {money(completed[0]['s'])}"
    )

@admin_router.message(F.text == "🛠 Режим тех. работ")
async def admin_maintenance(message: Message):
    if not admin_only_message(message):
        return
    settings = await get_settings()
    new_value = "false" if settings.get("maintenance", "false") == "true" else "true"
    await set_setting("maintenance", new_value)
    await message.answer(f"🛠 Режим тех. работ: {'ВКЛ' if new_value == 'true' else 'ВЫКЛ'}", reply_markup=admin_menu())

async def poll_bot_forever(bot: Bot, dp: Dispatcher):
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except TelegramConflictError:
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    tasks = []
    if shop_bot and SHOP_BOT_TOKEN:
        tasks.append(asyncio.create_task(poll_bot_forever(shop_bot, shop_dp)))
    if admin_bot and ADMIN_BOT_TOKEN:
        tasks.append(asyncio.create_task(poll_bot_forever(admin_bot, admin_dp)))
    yield
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if shop_bot:
        await shop_bot.session.close()
    if admin_bot:
        await admin_bot.session.close()

app = FastAPI(title="Mediapark Home Mini App", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
async def root():
    response = FileResponse(BASE_DIR / "index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/api/state")
async def api_state():
    settings = await get_settings()
    products = await get_products()
    return {"settings": settings, "products": products, "categories": CATEGORIES, "category_translations": CATEGORY_TRANSLATIONS, "subcategory_translations": SUBCATEGORY_TRANSLATIONS}

@app.post("/api/order")
async def api_order(payload: OrderPayload):
    product_rows = await db_execute("SELECT id,price,name_ru FROM products WHERE id IN (%s)" % ",".join("?" * len(payload.items)), tuple(i.id for i in payload.items), fetch=True)
    price_map = {p["id"]: p for p in product_rows}
    if len(price_map) != len(payload.items):
        raise HTTPException(400, "Некоторые товары больше не доступны.")
    calculated = 0
    normalized = []
    for item in payload.items:
        db_price = int(price_map[item.id]["price"])
        if item.price != db_price:
            raise HTTPException(409, "Цена товара изменилась. Обновите каталог.")
        line = db_price * item.quantity
        calculated += line
        normalized.append({"id": item.id, "name": price_map[item.id]["name_ru"], "price": db_price, "quantity": item.quantity})
    if calculated != payload.total:
        raise HTTPException(400, "Неверная сумма заказа.")
    order_id = await db_execute(
        "INSERT INTO orders(customer_name,phone,address,comment,items_json,total,status) VALUES(?,?,?,?,?,?,?)",
        (payload.customer_name, payload.phone, payload.address, payload.comment, json.dumps(normalized, ensure_ascii=False), calculated, "new"),
    )
    await send_order_to_admin(order_id, payload)
    return {"ok": True, "order_id": order_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
