import json
import logging
import os
from urllib.parse import quote

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from engine.sg.payout import fan_to_value, net_balances, settle_discard_win, settle_self_draw
from engine.sg.scoring import HandContext, score_hand
from engine.tiles import parse_tiles
from game_session import end_session, get_session, start_session

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_URL = os.environ.get("WEBAPP_URL")
BASE_UNIT = float(os.environ.get("BASE_UNIT", "0.10"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome to Mahjong Bot! Use /help to see available commands.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/newgame Alice, Bob, Carol, Dave - start a session with these 4 players\n"
        "/play - launch the Mini App to record a winning hand\n"
        "/balances - show current running balances\n"
        "/endgame - end the session\n"
        "/help - show this message"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.partition(" ")[2].strip()
    players = [p.strip() for p in text.split(",") if p.strip()]
    if len(players) != 4:
        await update.message.reply_text(
            "Usage: /newgame Alice, Bob, Carol, Dave (exactly 4 players for SG mahjong)"
        )
        return

    start_session(update.effective_chat.id, players)
    await update.message.reply_text(
        f"Session started with: {', '.join(players)}\nUse /play to record a winning hand."
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not WEBAPP_URL:
        await update.message.reply_text(
            "WEBAPP_URL is not set yet. Add it to .env once the Mini App is hosted."
        )
        return

    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session. Start one with /newgame first.")
        return

    url = f"{WEBAPP_URL}?players={quote(','.join(session.players))}"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="🀄 Record Winning Hand", web_app=WebAppInfo(url=url))]]
    )
    await update.message.reply_text("Tap below to enter the winning hand:", reply_markup=keyboard)


async def balances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session. Start one with /newgame first.")
        return

    lines = [f"{p}: {session.balances[p]:+.2f}" for p in session.players]
    await update.message.reply_text("Current balances:\n" + "\n".join(lines))


async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session.")
        return

    lines = [f"{p}: {session.balances[p]:+.2f}" for p in session.players]
    end_session(update.effective_chat.id)
    await update.message.reply_text("Session ended. Final balances:\n" + "\n".join(lines))


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session. Start one with /newgame first.")
        return

    data = json.loads(update.effective_message.web_app_data.data)

    try:
        tiles = parse_tiles(data["tiles"])
        ctx = HandContext(seat_wind=data["seat_wind"], round_wind=data["round_wind"])
        result = score_hand(tiles, ctx)
    except ValueError as e:
        await update.message.reply_text(f"Invalid hand: {e}")
        return

    value = fan_to_value(result.fan, base_unit=BASE_UNIT)
    winner = data["winner"]

    if data["self_draw"]:
        transfers = settle_self_draw(winner, value, players=session.players)
        method = "self-draw"
    else:
        transfers = settle_discard_win(winner, data["discarder"], value)
        method = f"off {data['discarder']}'s discard"

    session.apply_transfers(transfers)

    fan_lines = "\n".join(f"  {name}: {n}" for name, n in result.breakdown.items())
    transfer_lines = "\n".join(f"  {t.payer} → {t.payee}: {t.amount:.2f}" for t in transfers)
    balance_lines = "\n".join(f"  {p}: {session.balances[p]:+.2f}" for p in session.players)

    await update.message.reply_text(
        f"🀄 {winner} wins {method}!\n\n"
        f"Fan ({result.fan} total):\n{fan_lines or '  (chicken hand)'}\n\n"
        f"Payouts:\n{transfer_lines}\n\n"
        f"Balances:\n{balance_lines}"
    )


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("newgame", newgame))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("balances", balances))
    application.add_handler(CommandHandler("endgame", endgame))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
