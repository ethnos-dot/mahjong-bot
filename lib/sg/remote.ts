"use client";

// Client layer for the group-synced tracker. All calls go to the Supabase
// `track` Edge Function, which validates Telegram initData server-side.

import { Transfer } from "./payout";

const TRACK_URL = process.env.NEXT_PUBLIC_TRACK_URL || "";

export interface Tracker {
  id: string;
  code: string;
  game: string;
  name: string;
  players: string[];
  bases: { tai: number; yao: number; gang: number };
}

export interface RemoteAction {
  id: string;
  actioner: string;
  summary: string;
  transfers: Transfer[];
  created_at: string;
}

export interface TrackerState {
  tracker: Tracker;
  actions: RemoteAction[];
}

export const syncEnabled = () => Boolean(TRACK_URL);

function initData(): string {
  if (typeof window === "undefined") return "";
  return window.Telegram?.WebApp?.initData || "";
}

async function call<T>(op: string, payload: Record<string, unknown>): Promise<T> {
  if (!TRACK_URL) throw new Error("Sync isn't configured (NEXT_PUBLIC_TRACK_URL not set).");
  const res = await fetch(TRACK_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ op, initData: initData(), ...payload }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error || `request failed (${res.status})`);
  return data as T;
}

export const createTracker = (name: string, players: string[], bases: Tracker["bases"]) =>
  call<TrackerState>("create", { name, players, bases });

/** Fill in a bot-created group stub (code already exists, players still empty). */
export const setupGroup = (code: string, name: string, players: string[], bases: Tracker["bases"]) =>
  call<TrackerState>("setup-group", { code, name, players, bases });

export const getState = (code: string) => call<TrackerState>("state", { code });

export const addRemoteAction = (code: string, summary: string, transfers: Transfer[]) =>
  call<TrackerState>("action", { code, summary, transfers });

/** The winning-tile / join deep-link param Telegram passes when opened via
 *  t.me/<bot>/<app>?startapp=<code>. */
export function startParamCode(): string | null {
  if (typeof window === "undefined") return null;
  const sp = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
  return sp ? String(sp).toUpperCase() : null;
}

/** Bot username for building shareable deep links. Override via env if needed. */
export const BOT_APP_LINK = process.env.NEXT_PUBLIC_BOT_APP_LINK || "https://t.me/jpgmahjongbot/jpg";
