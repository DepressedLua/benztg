import asyncio
import json
import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
WEBAPP_URL = os.getenv("WEBAPP_URL")
PORT = int(os.getenv("PORT", "8000"))
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID", "0"))  # ID канала для хранения

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ID сообщения в канале (обновляется при старте)
storage_message_id = None

ads_storage = {"ads": [], "interval_hours": 4, "is_active": False, "subscribers": set()}

# ==================== ХРАНЕНИЕ В TELEGRAM ====================
async def get_comments_from_tg():
    """Читает комментарии из сообщения в канале"""
    global storage_message_id
    if not storage_message_id or not STORAGE_CHAT_ID:
        return {}
    try:
        msg = await bot.forward_message(
            chat_id=ADMIN_USER_ID,
            from_chat_id=STORAGE_CHAT_ID,
            message_id=storage_message_id
        )
        data = json.loads(msg.text or "{}")
        await bot.delete_message(ADMIN_USER_ID, msg.message_id)
        return data
    except Exception as e:
        logger.error(f"Ошибка чтения: {e}")
        return {}

async def save_comments_to_tg(data):
    """Сохраняет комментарии в сообщение в канале"""
    global storage_message_id
    text = json.dumps(data, ensure_ascii=False)
    try:
        if storage_message_id:
            await bot.edit_message_text(text, STORAGE_CHAT_ID, storage_message_id)
        else:
            msg = await bot.send_message(STORAGE_CHAT_ID, text)
            storage_message_id = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        msg = await bot.send_message(STORAGE_CHAT_ID, text)
        storage_message_id = msg.message_id

# ==================== API ====================
async def api_get_comments(request):
    sid = request.query.get('station_id')
    data = await get_comments_from_tg()
    if sid:
        return web.json_response({sid: data.get(sid, [])})
    return web.json_response(data)

async def api_add_comment(request):
    try:
        body = await request.json()
        sid = str(body['station_id'])
        comment = body['comment']
        
        data = await get_comments_from_tg()
        if sid not in data:
            data[sid] = []
        data[sid].append(comment)
        if len(data[sid]) > 200:
            data[sid] = data[sid][-200:]
        
        await save_comments_to_tg(data)
        return web.json_response({"success": True, "total": len(data[sid])})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# ==================== КЛАВИАТУРЫ ====================
def main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🗺 Открыть карту заправок", web_app=WebAppInfo(url=WEBAPP_URL))
    return kb.as_markup()

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🗺 Карта", web_app=WebAppInfo(url=WEBAPP_URL))
    kb.button(text="📢 Реклама", callback_data="ads_menu")
    kb.button(text="📊 Статистика", callback_data="stats")
    kb.adjust(1)
    return kb.as_markup()

# ==================== КОМАНДЫ ====================
@dp.message(Command("start"))
async def start(msg: types.Message):
    ads_storage["subscribers"].add(msg.from_user.id)
    if msg.from_user.id == ADMIN_USER_ID:
        await msg.answer("👑 Админ-панель", reply_markup=admin_kb())
    else:
        await msg.answer("⛽ <b>Бензин в Астрахани</b>\n\nГде есть топливо и очереди?\nНажмите кнопку:", reply_markup=main_kb(), parse_mode="HTML")

@dp.message(Command("admin"))
async def admin(msg: types.Message):
    if msg.from_user.id != ADMIN_USER_ID:
        return await msg.answer("⛔ Нет доступа")
    await msg.answer("👑 Админ-панель", reply_markup=admin_kb())

@dp.message(Command("stats"))
async def stats_cmd(msg: types.Message):
    data = await get_comments_from_tg()
    total = sum(len(v) for v in data.values())
    await msg.answer(f"📊 Статистика\n💬 Комментариев: {total}\n📍 Станций с отзывами: {len(data)}\n👥 Подписчиков: {len(ads_storage['subscribers'])}")

# ==================== CALLBACKS ====================
@dp.callback_query(F.data == "stats")
async def stats(cb: types.CallbackQuery):
    data = await get_comments_from_tg()
    total = sum(len(v) for v in data.values())
    await cb.message.edit_text(f"📊 Статистика\n💬 Комментариев: {total}\n👥 Подписчиков: {len(ads_storage['subscribers'])}")

# ==================== ЗАПУСК ====================
async def main():
    logger.info("Запуск...")
    
    # Ищем последнее сообщение в канале
    global storage_message_id
    if STORAGE_CHAT_ID:
        try:
            updates = await bot.get_updates(offset=-1, limit=1)
            logger.info(f"Канал для хранения: {STORAGE_CHAT_ID}")
        except:
            logger.warning("Не удалось подключиться к каналу")
    
    app = web.Application()
    app.router.add_get('/api/comments', api_get_comments)
    app.router.add_post('/api/comments', api_add_comment)
    app.router.add_get('/', lambda r: web.json_response({"status": "ok"}))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"API: порт {PORT}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
