"use client";

import { useEffect, useState } from "react";
import { useTelegram } from "@/lib/telegram";
import GamePicker from "@/components/GamePicker";
import RiichiCalculator from "@/components/RiichiCalculator";
import SGGame from "@/components/SGGame";

type Screen = "picker" | "riichi" | "sg";

export default function Page() {
  useTelegram(); // initialise the Telegram Mini App SDK (no-op in a plain browser)
  const [screen, setScreen] = useState<Screen | null>(null);

  // Resolve the initial screen from ?type=; default to the game picker. Done in
  // an effect so the prerendered HTML and first client render match (no flash).
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("type");
    setScreen(t === "riichi" ? "riichi" : t === "sg" ? "sg" : "picker");
  }, []);

  if (screen === null) return null;
  if (screen === "riichi") return <RiichiCalculator onBack={() => setScreen("picker")} />;
  if (screen === "sg") return <SGGame onBack={() => setScreen("picker")} />;
  return <GamePicker onPick={setScreen} />;
}
