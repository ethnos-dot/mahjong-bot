import json
import logging
import os
from urllib.parse import quote

from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from engine.riichi.analyze import CalledMeld, WinContext, analyze as riichi_analyze
from engine.riichi.scoring import score as riichi_score
from engine.sg.payout import (
    fan_to_value,
    settle_discard_win,
    settle_gang,
    settle_self_draw,
    settle_yao,
)
from game_session import end_session, get_session, start_session

# override=True so this bot's .env token wins over any global TELEGRAM_BOT_TOKEN
# (the machine has a global one for a different bot - without this it would clash).
load_dotenv(override=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_URL = os.environ.get("WEBAPP_URL")
DEFAULT_BASE = float(os.environ.get("BASE_UNIT", "0.10"))


# --- helpers ------------------------------------------------------------

def _fmt_transfers(session, transfers) -> str:
    fmt = (lambda a: f"{a:,.0f}") if session.game_type == "riichi" else (lambda a: f"{a:.2f}")
    return "\n".join(f"  {t.payer} → {t.payee}: {fmt(t.amount)}" for t in transfers)


def _fmt_balances(session) -> str:
    fmt = (lambda a: f"{a:+,.0f}") if session.game_type == "riichi" else (lambda a: f"{a:+.2f}")
    return "\n".join(f"  {p}: {fmt(session.balances[p])}" for p in session.players)


def _actioner_name(update: Update) -> str:
    u = update.effective_user
    return (u.full_name or u.username or str(u.id)) if u else "?"


def _parse_values(text: str) -> dict:
    """Parse 'tai 0.1 yao 0.2 gang 0.2' (any subset, any order) into a dict."""
    out = {}
    tokens = text.replace(",", " ").split()
    for i in range(len(tokens) - 1):
        key = tokens[i].lower()
        if key in ("tai", "yao", "gang"):
            try:
                out[f"{key}_base"] = float(tokens[i + 1])
            except ValueError:
                pass
    return out


# --- commands -----------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome to Mahjong Bot! Use /help to see available commands.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/newgame Alice, Bob, Carol, Dave - start a SG session (4 players)\n"
        "   optional values: /newgame Alice, Bob, Carol, Dave | tai 0.1 yao 0.2 gang 0.2\n"
        "/newriichi - open the riichi payout calculator (pure hand calc, no players/tracking)\n"
        "/play - reopen the input form (SG action menu / riichi calculator)\n"
        "/balances - show current running balances\n"
        "/log - show the chronological action log\n"
        "/endgame - end the session\n"
        "/help - show this message"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = update.message.text.partition(" ")[2]
    players_part, _, values_part = raw.partition("|")
    players = [p.strip() for p in players_part.split(",") if p.strip()]
    if len(players) != 4:
        await update.message.reply_text(
            "Usage: /newgame Alice, Bob, Carol, Dave (exactly 4 players for SG mahjong)\n"
            "Optional: ... | tai 0.1 yao 0.2 gang 0.2"
        )
        return

    values = _parse_values(values_part)
    session = start_session(
        update.effective_chat.id,
        players,
        tai_base=values.get("tai_base", DEFAULT_BASE),
        yao_base=values.get("yao_base", DEFAULT_BASE),
        gang_base=values.get("gang_base", DEFAULT_BASE),
    )
    await update.message.reply_text(
        f"Session started with: {', '.join(players)}\n"
        f"Values - tai: {session.tai_base:.2f}  yao(x): {session.yao_base:.2f}  "
        f"gang(y): {session.gang_base:.2f}\n"
        "Use /play to open the action menu."
    )


async def newriichi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not WEBAPP_URL:
        await update.message.reply_text(
            "WEBAPP_URL is not set yet. Add it to .env once the Mini App is hosted."
        )
        return
    # Pure calculator - no roster/players needed. Mark the chat as riichi so
    # /play reopens the calculator too.
    start_session(update.effective_chat.id, [], game_type="riichi")
    # NOTE: web_app_data only reaches the bot from a *reply keyboard* button
    # (sendData is unavailable from inline buttons / menu button / main app).
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(
            text="🀄 Open Riichi Calculator",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?type=riichi"),
        )]],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "Riichi payout calculator (pure hand calc - nothing tracked):",
        reply_markup=keyboard,
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

    if session.game_type == "riichi":
        url = f"{WEBAPP_URL}?type=riichi"
        label = "🀄 Open Riichi Calculator"
    else:
        url = f"{WEBAPP_URL}?players={quote(','.join(session.players))}"
        label = "🀄 Open Action Menu"
    # Reply-keyboard button: required for the Mini App's sendData to reach the bot.
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(text=label, web_app=WebAppInfo(url=url))]],
        resize_keyboard=True,
    )
    await update.message.reply_text("Tap below to record an action:", reply_markup=keyboard)


async def balances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session. Start one with /newgame first.")
        return
    if session.game_type == "riichi":
        await update.message.reply_text(
            "Riichi is a payout calculator only - no running balances are tracked."
        )
        return
    await update.message.reply_text("Current balances:\n" + _fmt_balances(session))


async def show_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session. Start one with /newgame first.")
        return
    if session.game_type == "riichi":
        await update.message.reply_text(
            "Riichi is a payout calculator only - nothing is logged."
        )
        return
    if not session.log:
        await update.message.reply_text("No actions recorded yet.")
        return
    lines = [f"{i + 1}. [{e.actioner}] {e.summary}" for i, e in enumerate(session.log)]
    await update.message.reply_text("Action log:\n" + "\n".join(lines))


async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session.")
        return
    if session.game_type == "riichi":
        end_session(update.effective_chat.id)
        await update.message.reply_text("Riichi calculator closed.")
        return
    out = _fmt_balances(session)
    end_session(update.effective_chat.id)
    await update.message.reply_text("Session ended. Final balances:\n" + out)


# --- action dispatch ----------------------------------------------------

def _build_action(session, data: dict):
    """Return (summary, transfers) for a submitted action, or raise ValueError."""
    action = data.get("action")

    if action == "hu":
        tai = int(data["tai"])
        winner, discarder = data["winner"], data["discarder"]
        value = fan_to_value(tai, base_unit=session.tai_base)
        transfers = settle_discard_win(winner, discarder, value)
        return f"Hu: {winner} wins off {discarder} ({tai} tai, {value:.2f})", transfers

    if action == "zimo":
        tai = int(data["tai"])
        winner = data["winner"]
        value = fan_to_value(tai, base_unit=session.tai_base)
        transfers = settle_self_draw(winner, value, players=session.players)
        return f"Zimo: {winner} self-draws ({tai} tai)", transfers

    if action == "gang":
        gtype = data["gang_type"]  # an | shoot | peng
        konger = data["konger"]
        shooter = data.get("shooter") if gtype == "shoot" else None
        transfers = settle_gang(konger, gtype, session.gang_base, session.players, shooter=shooter)
        label = {"an": "an gang", "shoot": "shoot gang", "peng": "gang after peng"}[gtype]
        who = f" off {shooter}" if shooter else ""
        return f"Gang: {konger} {label}{who}", transfers

    if action == "yao":
        ytype = data["yao_type"]  # an | hou
        biter = data["biter"]
        target = data.get("target") if data.get("scope") == "one" else None
        transfers = settle_yao(biter, ytype, session.yao_base, session.players, target=target)
        label = {"an": "an yao", "hou": "hou yao"}[ytype]
        who = f" on {target}" if target else " on everyone"
        return f"Yao: {biter} {label}{who}", transfers

    raise ValueError(f"unknown action: {action!r}")


def _calc_riichi(data: dict) -> str:
    """Pure hand calculator: given the hand + conditions, return a formatted
    result (point value + role-based payment breakdown). No players, no
    transfers - nothing is tracked.

    Two input paths:
    - Auto: payload has 'tiles' (+ optional 'called') => analyzer detects
      yaku/fu; dealer is implied by the winner's seat wind (East = dealer).
    - Manual: payload has 'han' + 'fu' + a 'dealer' boolean.
    """
    tsumo = bool(data["tsumo"])
    honba = int(data.get("honba", 0))
    players = int(data.get("players", 4))
    if players not in (3, 4):
        players = 4

    if "tiles" in data:
        seat_wind = data.get("seat_wind", "SW")   # East => dealer
        round_wind = data.get("round_wind", "EW")
        last_tile = bool(data.get("haitei"))
        ctx = WinContext(
            seat_wind=seat_wind,
            round_wind=round_wind,
            win_tile=data["win_tile"],
            tsumo=tsumo,
            riichi=bool(data.get("riichi", False)),
            double_riichi=bool(data.get("double_riichi", False)),
            ippatsu=bool(data.get("ippatsu", False)),
            haitei=last_tile and tsumo,
            houtei=last_tile and not tsumo,
            rinshan=bool(data.get("rinshan", False)),
            chankan=bool(data.get("chankan", False)),
            dora=int(data.get("dora", 0)),
            aka=int(data.get("aka", 0)),
            players=players,
            honba=honba,
        )
        called = [CalledMeld(m["kind"], tuple(m["codes"]), m.get("concealed", False))
                  for m in data.get("called", [])]
        result = riichi_analyze(data["tiles"], called, ctx)
        if not result.ok:
            raise ValueError(f"invalid hand: {result.error}")
        s = result.score
        han, fu = result.han, result.fu
        dealer = seat_wind == "EW"
        if result.yakuman:
            yaku_str = " + ".join(result.yakuman)
        else:
            yaku_str = ", ".join((n if h == 0 else f"{n} {h}han") for n, h in result.yaku)
        head = f"{yaku_str}\n" if yaku_str else ""
    else:
        dealer = bool(data.get("dealer", False))
        riichi_han = 1 if data.get("riichi") else 0
        han = int(data["han"]) + int(data.get("dora", 0)) + riichi_han
        fu = int(data.get("fu", 30))
        s = riichi_score(han, fu, dealer=dealer, tsumo=tsumo, players=players, honba=honba)
        head = ""

    # Role-based breakdown (no player names).
    lines = []
    for p in s.payments:
        if p.role == "discarder":
            lines.append(f"  Discarder pays {p.amount:,}")
        elif p.role == "dealer":
            lines.append(f"  Dealer pays {p.amount:,}")
        else:
            n = p.count
            verb = "pays" if n == 1 else "pay"
            each = " each" if n > 1 else ""
            lines.append(f"  {n} non-dealer{'s' if n > 1 else ''} {verb} {p.amount:,}{each}")

    seat = "dealer" if dealer else "non-dealer"
    win = "tsumo" if tsumo else "ron"
    limit = f" {s.limit}" if s.limit else ""
    fu_note = f" {fu}fu" if 0 < han < 5 else ""
    header = f"{seat} {win} — {han} han{fu_note}{limit} = {s.from_payments:,} total"
    return head + header + "\n" + "\n".join(lines)


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = json.loads(update.effective_message.web_app_data.data)
    actioner = _actioner_name(update)

    # Riichi is a pure hand calculator: no session needed - compute & show.
    if data.get("action") == "riichi":
        try:
            body = _calc_riichi(data)
        except (KeyError, ValueError) as e:
            await update.message.reply_text(f"Invalid hand: {e}")
            return
        await update.message.reply_text(f"🀄 Riichi calc\n{body}\n\n(by {actioner})")
        return

    # SG actions need an active session (players + running balances).
    session = get_session(update.effective_chat.id)
    if not session:
        await update.message.reply_text("No active session. Start one with /newgame first.")
        return

    try:
        summary, transfers = _build_action(session, data)
    except (KeyError, ValueError) as e:
        await update.message.reply_text(f"Invalid action: {e}")
        return

    session.record(actioner, summary, transfers)
    await update.message.reply_text(
        f"🀄 {summary}\n"
        f"(entered by {actioner})\n\n"
        f"Payouts:\n{_fmt_transfers(session, transfers)}\n\n"
        f"Balances:\n{_fmt_balances(session)}"
    )


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("newgame", newgame))
    application.add_handler(CommandHandler("newriichi", newriichi))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("balances", balances))
    application.add_handler(CommandHandler("log", show_log))
    application.add_handler(CommandHandler("endgame", endgame))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
