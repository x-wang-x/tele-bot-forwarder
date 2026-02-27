import asyncio
import json
import os
from collections import deque
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

CONFIG_FILE = "config.json"
MAX_QUEUE_SIZE = 500

queue = deque()
processing = False
success_count = 0
fail_count = 0

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"target_chat_id": None, "target_thread_id": None, "always_dl": False}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

async def process_queue(application, target_chat_id, target_thread_id=None):
    global processing, success_count, fail_count
    processing = True
    
    while queue:
        update = queue.popleft()
        try:
            await forward_message(application.bot, update, target_chat_id, target_thread_id)
            success_count += 1
        except Exception as e:
            fail_count += 1
        await asyncio.sleep(0.5)
    
    processing = False

async def forward_message(bot, update: Update, target_chat_id: int, target_thread_id=None):
    config = load_config()
    always_dl = config.get("always_dl", False)
    
    chat_id = update.effective_chat.id
    message = update.message
    
    if always_dl:
        await send_manually(bot, update, target_chat_id, target_thread_id)
        return
    
    try:
        await bot.forward_message(
            chat_id=target_chat_id,
            from_chat_id=chat_id,
            message_id=message.message_id,
            message_thread_id=target_thread_id
        )
    except Exception:
        await send_manually(bot, update, target_chat_id, target_thread_id)

async def send_manually(bot, update: Update, target_chat_id: int, target_thread_id=None):
    message = update.message
    
    if message.text:
        await bot.send_message(chat_id=target_chat_id, text=message.text, message_thread_id=target_thread_id)
    elif message.photo:
        photo = message.photo[-1]
        await bot.send_photo(chat_id=target_chat_id, photo=photo.file_id, caption=message.caption, message_thread_id=target_thread_id)
    elif message.video:
        await bot.send_video(chat_id=target_chat_id, video=message.video.file_id, caption=message.caption, message_thread_id=target_thread_id)
    elif message.document:
        await bot.send_document(chat_id=target_chat_id, document=message.document.file_id, caption=message.caption, message_thread_id=target_thread_id)
    elif message.audio:
        await bot.send_audio(chat_id=target_chat_id, audio=message.audio.file_id, caption=message.caption, message_thread_id=target_thread_id)
    elif message.voice:
        await bot.send_voice(chat_id=target_chat_id, voice=message.voice.file_id, caption=message.caption, message_thread_id=target_thread_id)
    elif message.sticker:
        await bot.send_sticker(chat_id=target_chat_id, sticker=message.sticker.file_id, message_thread_id=target_thread_id)
    elif message.animation:
        await bot.send_animation(chat_id=target_chat_id, animation=message.animation.file_id, caption=message.caption, message_thread_id=target_thread_id)
    elif message.video_note:
        await bot.send_video_note(chat_id=target_chat_id, video_note=message.video_note.file_id, message_thread_id=target_thread_id)
    else:
        raise Exception("Unsupported message type")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    config = load_config()
    target = config.get("target_chat_id")
    thread = config.get("target_thread_id")
    
    text = (
        "👋 Welcome to Forwarder Bot!\n\n"
        "Commands:\n"
        "/setchat <chat_id> - Set target chat\n"
        "/sendhere - Set target to current chat\n"
        "/check - Verify bot can send to target\n"
        "/status - Show current target chat\n"
        "/alwaysdl <0/1> - Toggle always download & re-upload\n"
        "/queue - Show queue status\n\n"
    )
    
    if target:
        text += f"Target: `{target}`"
        if thread:
            text += f"\nThread: `{thread}`"
    else:
        text += "No target chat set. Use /setchat <chat_id>"
    
    await update.message.reply_text(text)

async def setchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage: /setchat <chat_id>")
        return
    
    try:
        target_chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid chat ID. Must be a number.")
        return
    
    try:
        await context.bot.send_message(chat_id=target_chat_id, text="✅ Test message - Bot has access")
        config = load_config()
        config["target_chat_id"] = target_chat_id
        save_config(config)
        await update.message.reply_text(f"✅ Target chat set to: {target_chat_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Bot can't send message here: {e}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    config = load_config()
    target = config.get("target_chat_id")
    
    if not target:
        await update.message.reply_text("No target chat set. Use /setchat <chat_id>")
        return
    
    try:
        await context.bot.send_message(chat_id=target, text="✅ Test")
        await update.message.reply_text(f"✅ Bot can send to {target}")
    except Exception as e:
        await update.message.reply_text(f"❌ Bot can't send to {target}: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    config = load_config()
    target = config.get("target_chat_id")
    thread = config.get("target_thread_id")
    
    if target:
        text = f"Target: `{target}`"
        if thread:
            text += f"\nThread: `{thread}`"
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text("No target chat set. Use /setchat <chat_id>")

async def current_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(str(update.effective_chat.id))

async def sendhere_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id
    
    try:
        await context.bot.send_message(chat_id=chat_id, text="✅", message_thread_id=thread_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Bot can't send here: {e}")
        return
    
    config = load_config()
    config["target_chat_id"] = chat_id
    config["target_thread_id"] = thread_id
    save_config(config)
    
    await update.message.reply_text("✅")

async def alwaysdl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        config = load_config()
        current = config.get("always_dl", False)
        await update.message.reply_text(f"Always download: {current}")
        return
    
    value = context.args[0]
    if value not in ["0", "1"]:
        await update.message.reply_text("Usage: /alwaysdl <0 or 1>")
        return
    
    always_dl = value == "1"
    config = load_config()
    config["always_dl"] = always_dl
    save_config(config)
    await update.message.reply_text(f"Always download: {always_dl}")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    global processing, success_count, fail_count
    await update.message.reply_text(
        f"Queue: {len(queue)}/{MAX_QUEUE_SIZE}\n"
        f"Success: {success_count}\n"
        f"Failed: {fail_count}\n"
        f"Processing: {processing}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    config = load_config()
    target = config.get("target_chat_id")
    target_thread = config.get("target_thread_id")
    
    if not target:
        await update.message.reply_text(
            "⚠️ No target chat set.\nUse /setchat <chat_id> to set target."
        )
        return
    
    if len(queue) >= MAX_QUEUE_SIZE:
        await update.message.reply_text("⚠️ Queue full, please wait...")
        return
    
    queue.append(update)
    
    if not processing:
        asyncio.create_task(process_queue(context.application, target, target_thread))

def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set in .env")
        return
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("setchat", setchat_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("queue", queue_command))
    application.add_handler(CommandHandler("alwaysdl", alwaysdl_command))
    application.add_handler(CommandHandler("current", current_command))
    application.add_handler(CommandHandler("sendhere", sendhere_command))
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
