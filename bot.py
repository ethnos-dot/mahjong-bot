import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_URL = os.environ.get("WEBAPP_URL")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome to Mahjong Bot! Use /help to see available commands.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n/start - Start the bot\n/help - Show this message\n/play - Launch the Mahjong Mini App"
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not WEBAPP_URL:
        await update.message.reply_text(
            "WEBAPP_URL is not set yet. Add it to .env once the Mini App is hosted."
        )
        return

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="🀄 Play Mahjong", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    await update.message.reply_text("Tap below to launch the Mini App:", reply_markup=keyboard)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("play", play))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
