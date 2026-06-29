"use client";

import { useMemo, useState } from "react";
import { analyze, WinContext } from "@/lib/riichi/analyze";
import ResultCard from "./ResultCard";

const SUITS: [string, string, string][] = [
  ["C", "m", "Man"],
  ["D", "p", "Pin"],
  ["B", "s", "Sou"],
];
const HONORS: [string, string][] = [
  ["EW", "East"],
  ["SW", "South"],
  ["WW", "West"],
  ["NW", "North"],
  ["WD", "Wh"],
  ["GD", "Gr"],
  ["RD", "Rd"],
];
const tileLabel = (code: string): string => {
  const s = SUITS.find((x) => x[0] === code[1]);
  if (s && /\d/.test(code[0])) return `${code[0]}${s[1]}`;
  return HONORS.find((h) => h[0] === code)?.[1] ?? code;
};

const WINDS = [
  ["EW", "East"],
  ["SW", "South"],
  ["WW", "West"],
  ["NW", "North"],
];
const FLAGS: [string, string][] = [
  ["riichi", "Riichi"],
  ["double_riichi", "Dbl Riichi"],
  ["ippatsu", "Ippatsu"],
  ["haitei", "Haitei/Houtei"],
  ["rinshan", "Rinshan"],
  ["chankan", "Chankan"],
];
const RANGE = (n: number) => Array.from({ length: n }, (_, i) => i);

export default function TilesMode({
  tsumo,
  players,
  honba,
}: {
  tsumo: boolean;
  players: number;
  honba: number;
}) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [winTile, setWinTile] = useState<string | null>(null);
  const [seatWind, setSeatWind] = useState("EW");
  const [roundWind, setRoundWind] = useState("EW");
  const [flags, setFlags] = useState<Set<string>>(new Set());
  const [dora, setDora] = useState(0);

  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  const add = (code: string) => {
    if (total >= 14 || (counts[code] || 0) >= 4) return;
    setCounts((c) => ({ ...c, [code]: (c[code] || 0) + 1 }));
  };
  const remove = (code: string) => {
    setCounts((c) => {
      const n = (c[code] || 0) - 1;
      const next = { ...c };
      if (n <= 0) {
        delete next[code];
        if (winTile === code) setWinTile(null);
      } else next[code] = n;
      return next;
    });
  };
  const toggleFlag = (f: string) =>
    setFlags((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else {
        next.add(f);
        if (f === "riichi") next.delete("double_riichi");
        if (f === "double_riichi") next.delete("riichi");
      }
      return next;
    });

  const result = useMemo(() => {
    if (total !== 14 || !winTile) return null;
    const concealed: string[] = [];
    for (const [code, n] of Object.entries(counts)) for (let i = 0; i < n; i++) concealed.push(code);
    const last = flags.has("haitei");
    const ctx: WinContext = {
      seatWind,
      roundWind,
      winTile,
      tsumo,
      players,
      honba,
      riichi: flags.has("riichi"),
      doubleRiichi: flags.has("double_riichi"),
      ippatsu: flags.has("ippatsu"),
      haitei: last && tsumo,
      houtei: last && !tsumo,
      rinshan: flags.has("rinshan"),
      chankan: flags.has("chankan"),
      dora,
    };
    return analyze(concealed, [], ctx);
  }, [counts, winTile, seatWind, roundWind, flags, dora, tsumo, players, honba, total]);

  const selectedCodes = Object.keys(counts);

  return (
    <div>
      <h2>Seat wind <small>(East = dealer)</small></h2>
      <div className="row">
        {WINDS.map(([v, l]) => (
          <div key={v} className={"chip" + (seatWind === v ? " selected" : "")} onClick={() => setSeatWind(v)}>
            {l}
          </div>
        ))}
      </div>

      <h2>Round wind</h2>
      <div className="row">
        {WINDS.slice(0, 2).map(([v, l]) => (
          <div key={v} className={"chip" + (roundWind === v ? " selected" : "")} onClick={() => setRoundWind(v)}>
            {l}
          </div>
        ))}
      </div>

      <h2>Flags</h2>
      <div className="row">
        {FLAGS.map(([f, l]) => (
          <div key={f} className={"chip" + (flags.has(f) ? " on" : "")} onClick={() => toggleFlag(f)}>
            {l}
          </div>
        ))}
      </div>

      <h2>Dora (incl. aka / ura)</h2>
      <div className="row">
        {RANGE(11).map((n) => (
          <div key={n} className={"chip" + (dora === n ? " selected" : "")} onClick={() => setDora(n)}>
            {n}
          </div>
        ))}
      </div>

      <h2>Hand tiles ({total} / 14)</h2>
      {SUITS.map(([code]) => (
        <div className="tiles-grid" key={code}>
          {RANGE(9).map((i) => {
            const c = `${i + 1}${code}`;
            const n = counts[c] || 0;
            return (
              <div key={c} className={"tile-btn" + (n ? " has" : "")} onClick={() => add(c)}>
                {tileLabel(c)}
                {n > 0 && <span className="tile-badge">{n}</span>}
              </div>
            );
          })}
        </div>
      ))}
      <div className="tiles-grid">
        {HONORS.map(([c]) => {
          const n = counts[c] || 0;
          return (
            <div key={c} className={"tile-btn" + (n ? " has" : "")} onClick={() => add(c)}>
              {tileLabel(c)}
              {n > 0 && <span className="tile-badge">{n}</span>}
            </div>
          );
        })}
      </div>

      {selectedCodes.length > 0 && (
        <>
          <h2>Selected (tap to remove)</h2>
          <div className="row">
            {selectedCodes.flatMap((c) =>
              RANGE(counts[c]).map((i) => (
                <div key={`${c}-${i}`} className="chip" onClick={() => remove(c)}>
                  {tileLabel(c)}
                </div>
              )),
            )}
          </div>
        </>
      )}

      {total === 14 && (
        <>
          <h2>Winning tile</h2>
          <div className="row">
            {selectedCodes.map((c) => (
              <div key={c} className={"chip" + (winTile === c ? " selected" : "")} onClick={() => setWinTile(c)}>
                {tileLabel(c)}
              </div>
            ))}
          </div>
        </>
      )}

      {result &&
        (result.ok ? (
          <ResultCard score={result.score} yaku={result.yaku} yakuman={result.yakuman} />
        ) : (
          <ResultCard error={result.error} />
        ))}
    </div>
  );
}
