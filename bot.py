import asyncio
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


BOT_TOKEN = "8936287356:AAETg9k-oPkXzqPSpu5Rl0UisV1vo_BbT0Q"
ADMIN_USER_ID = 5454940943  # Твой Telegram ID
WEBAPP_URL = "https://depressedlua.github.io/benzhtml/"  # URL GitHub Pages

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище рекламных объявлений (в реальном проекте - БД)
ads_storage = {
    "ads": [],  # Список рекламных постов
    "interval_hours": 4,  # Интервал рассылки в часах
    "is_active": False,  # Активна ли рассылка
    "subscribers": set()  # ID подписчиков
}

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    """Основная клавиатура для всех пользователей"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🗺 Открыть карту заправок", web_app=WebAppInfo(url=WEBAPP_URL))
    return kb.as_markup()

def get_admin_keyboard():
    """Клавиатура админ-панели (только для ADMIN_USER_ID)"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🗺 Карта заправок", web_app=WebAppInfo(url=WEBAPP_URL))
    kb.button(text="📢 Управление рекламой", callback_data="admin_ads_menu")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.adjust(1)
    return kb.as_markup()

def get_ads_menu_keyboard():
    """Меню управления рекламой"""
    kb = InlineKeyboardBuilder()
    status = "✅ Активна" if ads_storage["is_active"] else "❌ Неактивна"
    kb.button(text=f"Статус рассылки: {status}", callback_data="ads_toggle")
    kb.button(text="➕ Добавить рекламу", callback_data="ads_add")
    kb.button(text="📋 Список рекламы", callback_data="ads_list")
    kb.button(text=f"⏱ Интервал: {ads_storage['interval_hours']}ч", callback_data="ads_interval")
    kb.button(text="👥 Подписчики", callback_data="ads_subscribers")
    kb.button(text="🔙 Назад", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик /start"""
    user_id = message.from_user.id
    
    # Добавляем пользователя в список подписчиков (можно сделать опциональным)
    ads_storage["subscribers"].add(user_id)
    
    if user_id == ADMIN_USER_ID:
        await message.answer(
            "👑 <b>Админ-панель АЗС Астрахань</b>\n\n"
            "Управляйте картой, рекламой и рассылками.",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "⛽ <b>Бензин в Астрахани</b>\n\n"
            "Узнайте, где есть топливо и какие очереди!\n"
            "Нажмите на кнопку ниже, чтобы открыть карту.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Скрытая команда для вызова админ-панели"""
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        "👑 <b>Админ-панель активирована</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )

@dp.message(Command("map"))
async def cmd_map(message: types.Message):
    """Открыть карту (для удобства)"""
    await message.answer(
        "🗺 Нажмите кнопку, чтобы открыть карту:",
        reply_markup=get_main_keyboard()
    )

# ==================== CALLBACK ОБРАБОТЧИКИ ====================

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👑 <b>Админ-панель АЗС Астрахань</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_ads_menu")
async def admin_ads_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Управление рекламой</b>\n\n"
        f"Статус: {'✅ Активна' if ads_storage['is_active'] else '❌ Неактивна'}\n"
        f"Интервал: каждые {ads_storage['interval_hours']} ч.\n"
        f"Подписчиков: {len(ads_storage['subscribers'])}\n"
        f"Рекламных постов: {len(ads_storage['ads'])}",
        reply_markup=get_ads_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "ads_toggle")
async def ads_toggle(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    ads_storage["is_active"] = not ads_storage["is_active"]
    status = "✅ Активна" if ads_storage["is_active"] else "❌ Неактивна"
    
    await callback.message.edit_text(
        f"📢 <b>Управление рекламой</b>\n\n"
        f"Статус изменён: {status}",
        reply_markup=get_ads_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer(f"Рассылка {status}")

@dp.callback_query(F.data == "ads_add")
async def ads_add(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 <b>Добавление рекламы</b>\n\n"
        "Отправьте рекламный пост (текст, фото, видео) следующим сообщением.\n"
        "Для отмены нажмите /cancel",
        parse_mode="HTML"
    )
    # Здесь нужно реализовать состояние FSM, но для простоты оставим заглушку
    await callback.answer()

@dp.callback_query(F.data == "ads_list")
async def ads_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    if not ads_storage["ads"]:
        await callback.answer("Список пуст", show_alert=True)
        return
    
    text = "📋 <b>Рекламные посты:</b>\n\n"
    for i, ad in enumerate(ads_storage["ads"], 1):
        preview = ad[:50] + "..." if len(ad) > 50 else ad
        text += f"{i}. {preview}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "ads_interval")
async def ads_interval(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    # Простой выбор интервала
    kb = InlineKeyboardBuilder()
    for h in [2, 4, 6, 8, 12, 24]:
        kb.button(text=f"{h} ч.", callback_data=f"ads_set_interval_{h}")
    kb.button(text="🔙 Назад", callback_data="admin_ads_menu")
    kb.adjust(3)
    
    await callback.message.edit_text(
        "⏱ Выберите интервал рассылки:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("ads_set_interval_"))
async def ads_set_interval(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    hours = int(callback.data.split("_")[-1])
    ads_storage["interval_hours"] = hours
    
    await callback.message.edit_text(
        f"⏱ Интервал установлен: <b>каждые {hours} ч.</b>",
        reply_markup=get_ads_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer(f"Интервал: {hours}ч")

@dp.callback_query(F.data == "ads_subscribers")
async def ads_subscribers(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    count = len(ads_storage["subscribers"])
    await callback.message.edit_text(
        f"👥 <b>Подписчики рассылки</b>\n\n"
        f"Всего: {count}\n"
        f"ID: {', '.join(map(str, list(ads_storage['subscribers'])[:20]))}" + 
        ("..." if count > 20 else ""),
        reply_markup=get_ads_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    # Здесь в реальном проекте собираем статистику из БД
    await callback.message.edit_text(
        "📊 <b>Статистика</b>\n\n"
        f"Подписчиков: {len(ads_storage['subscribers'])}\n"
        f"Рекламных постов: {len(ads_storage['ads'])}\n"
        f"Рассылка: {'✅ Активна' if ads_storage['is_active'] else '❌ Неактивна'}\n"
        f"Интервал: каждые {ads_storage['interval_hours']} ч.\n\n"
        "<i>Детальная статистика по АЗС будет доступна после интеграции с БД</i>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== РАССЫЛКА ====================

async def send_ads_to_all():
    """Фоновая задача рассылки рекламы"""
    while True:
        if ads_storage["is_active"] and ads_storage["ads"] and ads_storage["subscribers"]:
            # Берём следующую рекламу по кругу
            ad_index = int(datetime.now().timestamp() // (ads_storage["interval_hours"] * 3600)) % len(ads_storage["ads"])
            ad_content = ads_storage["ads"][ad_index]
            
            for user_id in ads_storage["subscribers"]:
                try:
                    await bot.send_message(
                        user_id,
                        f"📢 <b>Реклама</b>\n\n{ad_content}\n\n"
                        f"🗺 <i>Открыть карту: /map</i>",
                        parse_mode="HTML",
                        reply_markup=get_main_keyboard()
                    )
                    await asyncio.sleep(0.05)  # Защита от flood
                except Exception as e:
                    logger.error(f"Ошибка отправки {user_id}: {e}")
        
        # Ждём интервал
        await asyncio.sleep(ads_storage["interval_hours"] * 3600)

# ==================== ЗАПУСК ====================

async def main():
    logger.info("Бот запущен")
    
    # Запускаем фоновую задачу рассылки
    asyncio.create_task(send_ads_to_all())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
