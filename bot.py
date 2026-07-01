import asyncio
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
WEBAPP_URL = os.getenv("WEBAPP_URL")
PORT = int(os.getenv("PORT", "8000"))

COMMENTS_FILE = Path("comments.json")
ADS_FILE = Path("ads.json")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== ДАННЫЕ ====================
def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except:
            return default
    return default

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

comments_db = load_json(COMMENTS_FILE, {})
ads_storage = load_json(ADS_FILE, {
    "ads": [],
    "interval_hours": 4,
    "is_active": False,
    "subscribers": []
})
ads_storage["subscribers"] = set(ads_storage.get("subscribers", []))

def save_ads():
    save_json(ADS_FILE, {**ads_storage, "subscribers": list(ads_storage["subscribers"])})

# ==================== API ====================
async def api_get_comments(request):
    sid = request.query.get('station_id')
    if sid:
        return web.json_response({sid: comments_db.get(sid, [])})
    return web.json_response(comments_db)

async def api_add_comment(request):
    try:
        body = await request.json()
        sid = str(body['station_id'])
        comment = body['comment']
        if sid not in comments_db:
            comments_db[sid] = []
        comments_db[sid].append(comment)
        if len(comments_db[sid]) > 200:
            comments_db[sid] = comments_db[sid][-200:]
        save_json(COMMENTS_FILE, comments_db)
        return web.json_response({"success": True, "total": len(comments_db[sid])})
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

def ads_menu_kb():
    kb = InlineKeyboardBuilder()
    s = "✅ Активна" if ads_storage["is_active"] else "❌ Неактивна"
    kb.button(text=f"Статус: {s}", callback_data="ads_toggle")
    kb.button(text="➕ Добавить рекламу", callback_data="ads_add")
    kb.button(text="📋 Список", callback_data="ads_list")
    kb.button(text=f"⏱ Интервал: {ads_storage['interval_hours']}ч", callback_data="ads_interval")
    kb.button(text="👥 Подписчики", callback_data="ads_subscribers")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

# ==================== КОМАНДЫ ====================
@dp.message(Command("start"))
async def start(msg: types.Message):
    ads_storage["subscribers"].add(msg.from_user.id)
    save_ads()
    if msg.from_user.id == ADMIN_USER_ID:
        await msg.answer("👑 Админ-панель", reply_markup=admin_kb())
    else:
        await msg.answer("⛽ <b>Бензин в Астрахани</b>\n\nГде есть топливо и очереди?\nНажмите кнопку:", reply_markup=main_kb(), parse_mode="HTML")

@dp.message(Command("admin"))
async def admin(msg: types.Message):
    if msg.from_user.id != ADMIN_USER_ID:
        return await msg.answer("⛔ Нет доступа")
    await msg.answer("👑 Админ-панель", reply_markup=admin_kb())

# ==================== CALLBACKS ====================
@dp.callback_query(F.data == "back")
async def back(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    await cb.message.edit_text("👑 Админ-панель", reply_markup=admin_kb())

@dp.callback_query(F.data == "ads_menu")
async def ads_menu(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    await cb.message.edit_text(
        f"📢 Реклама\nСтатус: {'✅' if ads_storage['is_active'] else '❌'}\n"
        f"Постов: {len(ads_storage['ads'])}\nПодписчиков: {len(ads_storage['subscribers'])}",
        reply_markup=ads_menu_kb())

@dp.callback_query(F.data == "ads_toggle")
async def ads_toggle(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    ads_storage["is_active"] = not ads_storage["is_active"]
    save_ads()
    await cb.answer(f"{'✅ Вкл' if ads_storage['is_active'] else '❌ Выкл'}")
    await ads_menu(cb)

@dp.callback_query(F.data == "ads_add")
async def ads_add(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    await cb.message.edit_text("📝 Отправьте текст рекламы:")

@dp.message(F.text & ~F.text.startswith("/"), lambda msg: msg.from_user.id == ADMIN_USER_ID)
async def catch_ad(msg: types.Message):
    ads_storage["ads"].append(msg.html_text)
    save_ads()
    await msg.answer(f"✅ Добавлено! Всего: {len(ads_storage['ads'])}")

@dp.callback_query(F.data == "ads_list")
async def ads_list(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    if not ads_storage["ads"]:
        return await cb.answer("Список пуст")
    text = "\n\n".join(f"{i}. {ad[:100]}" for i, ad in enumerate(ads_storage["ads"], 1))
    await cb.message.edit_text(text)

@dp.callback_query(F.data == "ads_interval")
async def ads_interval(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    kb = InlineKeyboardBuilder()
    for h in [2,4,6,8,12,24]:
        kb.button(text=f"{h}ч", callback_data=f"int_{h}")
    kb.button(text="🔙 Назад", callback_data="ads_menu")
    kb.adjust(3)
    await cb.message.edit_text("⏱ Интервал:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("int_"))
async def set_interval(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    ads_storage["interval_hours"] = int(cb.data.split("_")[1])
    save_ads()
    await cb.answer(f"Интервал: {ads_storage['interval_hours']}ч")

@dp.callback_query(F.data == "ads_subscribers")
async def ads_subscribers(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    count = len(ads_storage["subscribers"])
    ids = list(ads_storage["subscribers"])[:30]
    text = f"👥 Подписчики: {count}\n\n" + "\n".join(f"• <code>{uid}</code>" for uid in ids)
    if count > 30: text += f"\n... и ещё {count - 30}"
    await cb.message.edit_text(text, parse_mode="HTML")

@dp.callback_query(F.data == "stats")
async def stats(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID: return
    total = sum(len(v) for v in comments_db.values())
    await cb.message.edit_text(
        f"📊 Статистика\n\n👥 Подписчиков: {len(ads_storage['subscribers'])}\n"
        f"📢 Постов: {len(ads_storage['ads'])}\n"
        f"💬 Комментариев: {total}\n"
        f"🔄 Рассылка: {'✅' if ads_storage['is_active'] else '❌'}"
    )

# ==================== РАССЫЛКА ====================
async def broadcaster():
    while True:
        if ads_storage["is_active"] and ads_storage["ads"] and ads_storage["subscribers"]:
            ad = ads_storage["ads"][int(datetime.now().timestamp() // (ads_storage["interval_hours"]*3600)) % len(ads_storage["ads"])]
            for uid in list(ads_storage["subscribers"]):
                try:
                    await bot.send_message(uid, f"📢 {ad}\n\n🗺 /map", parse_mode="HTML")
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.error(f"Ошибка {uid}: {e}")
        await asyncio.sleep(ads_storage["interval_hours"] * 3600)

# ==================== ЗАПУСК ====================
async def main():
    logger.info("Запуск...")
    asyncio.create_task(broadcaster())

    app = web.Application()
    app.router.add_get('/api/comments', api_get_comments)
    app.router.add_post('/api/comments', api_add_comment)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"API: порт {PORT}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
