import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp

# Загружаем переменные из .env файла, если он есть (для локального запуска)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)

# Токен берется исключительно из окружения — в коде его нет, на GitHub он не попадет
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ Ошибка: не найден BOT_TOKEN в переменных окружения!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

url_storage = {}

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Отправь мне ссылку на TikTok, и я скачаю видео без водяного знака."
    )

@dp.message(F.text.contains("tiktok.com") | F.text.contains("vt.tiktok.com"))
async def handle_tiktok_link(message: types.Message):
    url = message.text.strip()
    
    url_id = str(hash(url))
    url_storage[url_id] = url

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Видео без водяного знака", callback_data=f"vid:{url_id}"),
            InlineKeyboardButton(text="🎵 Аудио из TikTok", callback_data=f"aud:{url_id}")
        ]
    ])

    await message.answer("Что именно нужно сделать с этим роликом?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith(("vid:", "aud:")))
async def process_download(callback: CallbackQuery):
    action, url_id = callback.data.split(":")
    url = url_storage.get(url_id)

    if not url:
        await callback.message.edit_text("❌ Ссылка устарела. Отправь её заново.")
        return

    await callback.message.edit_text("⏳ Скачиваю из TikTok...")
    
    user_id = callback.from_user.id
    os.makedirs("downloads", exist_ok=True)

    if action == "vid":
        output_template = f"downloads/tiktok_{user_id}.mp4"
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'quiet': True,
        }
    else:
        output_template = f"downloads/tiktok_{user_id}.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"downloads/tiktok_{user_id}",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

    try:
        loop = asyncio.get_running_loop()
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        await loop.run_in_executor(None, download)

        real_file = None
        for f in os.listdir("downloads"):
            if str(user_id) in f:
                real_file = os.path.join("downloads", f)
                break

        if real_file and os.path.exists(real_file):
            if action == "vid":
                await callback.message.answer_video(FSInputFile(real_file), caption="Готово! 🎬")
            else:
                await callback.message.answer_audio(FSInputFile(real_file), caption="Твой трек из TikTok! 🎵")
            
            await callback.message.delete()
            os.remove(real_file)
        else:
            await callback.message.edit_text("❌ Не удалось найти видео. Возможно, ссылка недействительна.")

    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при скачивании.")

@dp.message()
async def other_messages(message: types.Message):
    await message.answer("Пожалуйста, отправь корректную ссылку на TikTok.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
