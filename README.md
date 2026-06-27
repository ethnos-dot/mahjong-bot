# Mahjong Bot

A Telegram bot for playing Mahjong, built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot).

## Setup

1. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Create a `.env` file with your bot token and Mini App URL:
   ```
   TELEGRAM_BOT_TOKEN=your-token-here
   WEBAPP_URL=https://your-deployed-app-url/
   ```
3. Run the bot:
   ```
   python bot.py
   ```

## Mini App (docs/)

`docs/index.html` is the page Telegram opens inside the app when a user taps the "Play Mahjong" button. It's served via GitHub Pages (Settings → Pages → Deploy from branch `main`, folder `/docs`). It must be HTTPS — `localhost` and plain HTTP won't work.

Once deployed, set `WEBAPP_URL` in `.env` to that page's URL.

## Enabling group use + Mini App in BotFather

1. Message [@BotFather](https://t.me/BotFather) → `/mybots` → select your bot.
2. **Bot Settings → Group Privacy** → turn **off** if you want the bot to see all group messages (not required just for commands/buttons).
3. **Bot Settings → Allow Groups?** → make sure it's enabled so the bot can be added to groups.
4. **Bot Settings → Menu Button** → set a Web App URL (your `WEBAPP_URL`) so a persistent "launch" button appears next to the message box. This also works inside groups.
5. (Optional) `/newapp` lets you register a full Mini App with its own name/icon, separate from the menu button.

Once configured, add the bot to a group as normal, and use `/play` (or the menu button) to launch the Mini App from there.
