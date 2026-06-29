"use client";

import { useEffect, useState } from "react";

// Minimal typing for the bits of the Telegram WebApp SDK we use.
interface TelegramWebApp {
  ready: () => void;
  expand: () => void;
  initData: string;
  initDataUnsafe?: {
    user?: { id: number; first_name?: string; username?: string };
    start_param?: string;
  };
  colorScheme?: "light" | "dark";
  themeParams?: Record<string, string>;
  setHeaderColor?: (c: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export interface TelegramState {
  ready: boolean;
  inTelegram: boolean;
  initData: string; // raw initData string - send to a backend to validate (HMAC) when one exists
  user: { id: number; name: string } | null;
}

/**
 * Initialises the Telegram Mini App SDK (ready/expand) and surfaces initData +
 * the current user. Works outside Telegram too (inTelegram=false) so the app
 * is usable in a plain browser during development.
 */
export function useTelegram(): TelegramState {
  const [state, setState] = useState<TelegramState>({
    ready: false,
    inTelegram: false,
    initData: "",
    user: null,
  });

  useEffect(() => {
    const wa = window.Telegram?.WebApp;
    if (wa) {
      try {
        wa.ready();
        wa.expand();
      } catch {
        /* ignore */
      }
      const u = wa.initDataUnsafe?.user;
      setState({
        ready: true,
        inTelegram: Boolean(wa.initData),
        initData: wa.initData || "",
        user: u ? { id: u.id, name: u.first_name || u.username || String(u.id) } : null,
      });
    } else {
      setState((s) => ({ ...s, ready: true }));
    }
  }, []);

  return state;
}
