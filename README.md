# mahjong-web

A Telegram Mini App for mahjong payouts, built as a **client-side web app** so it
works from *any* launch method — menu button, the Main Mini App (`/newapp`),
direct link, or in groups. Nothing depends on `sendData` (which only works from
a reply-keyboard button).

## Why this architecture

The earlier version was a static page that sent the hand to the bot via
`Telegram.WebApp.sendData`, and the bot replied. But `sendData` only works when
the Mini App is launched from a **reply-keyboard button** — not inline buttons,
the menu button, or the Main Mini App. So that approach can't be opened
standalone or in groups.

Here the scoring engine is ported to **TypeScript and runs in the browser**, so
the app computes and shows the result itself. No round-trip to the bot is needed
for a calculator. (A shared, multi-player tracker like Singaporean mode will add
a backend that validates `initData` — the standard Mini App pattern — but the
calculator needs none of that.)

## Stack

- **Next.js 15** (App Router) + **React 19** + TypeScript, `output: "export"`
  (static) so it deploys to GitHub Pages or any static host.
- Telegram WebApp SDK loaded in `app/layout.tsx`; `lib/telegram.ts` exposes a
  `useTelegram()` hook (theme, `initData`, user). Works in a plain browser too.

## Layout

- `lib/riichi/` — scoring engine ported from the Python `engine/riichi`
  (`scoring.ts`, `yaku.ts`).
- `components/RiichiCalculator.tsx` — riichi calculator (Han+Fu or pick-yaku),
  role-based payout, fully client-side.
- `components/GamePicker.tsx` — landing menu (Singaporean / Riichi).
- `app/page.tsx` — resolves `?type=` or shows the picker.

## Run / build

```
npm install
npm run dev      # http://localhost:3000  (use ?type=riichi to skip the picker)
npm run build    # static export to ./out
```

## Status

- Riichi calculator: done (manual + yaku-checklist, client-side).
- TODO: port the riichi from-tiles analyzer; port Singaporean (engine + a
  backend with `initData` validation for shared group balances); deploy.
