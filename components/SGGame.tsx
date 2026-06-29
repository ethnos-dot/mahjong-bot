"use client";

import { useState } from "react";
import { useLocalStorage } from "@/lib/useLocalStorage";
import {
  Transfer,
  fanToValue,
  settleDiscardWin,
  settleSelfDraw,
  settleYao,
  settleGang,
  applyTransfers,
} from "@/lib/sg/payout";

interface SGState {
  players: string[];
  tai: number;
  yao: number;
  gang: number;
  balances: Record<string, number>;
  log: { summary: string; transfers: Transfer[] }[];
}

const TAI = Array.from({ length: 10 }, (_, i) => i + 1);

function Chips({ options, value, onChange }: { options: { v: string; label: string }[]; value: string | null; onChange: (v: string) => void }) {
  return (
    <div className="row">
      {options.map((o) => (
        <div key={o.v} className={"chip" + (value === o.v ? " selected" : "")} onClick={() => onChange(o.v)}>
          {o.label}
        </div>
      ))}
    </div>
  );
}

export default function SGGame({ onBack }: { onBack: () => void }) {
  const [game, setGame, loaded] = useLocalStorage<SGState | null>("mahjong-sg", null);
  if (!loaded) return null;
  if (!game) return <Setup onStart={setGame} onBack={onBack} />;
  return <Play game={game} setGame={setGame} onBack={onBack} />;
}

function Setup({ onStart, onBack }: { onStart: (s: SGState) => void; onBack: () => void }) {
  const [names, setNames] = useState(["", "", "", ""]);
  const [tai, setTai] = useState("0.10");
  const [yao, setYao] = useState("0.20");
  const [gang, setGang] = useState("0.20");
  const ready = names.every((n) => n.trim());

  const start = () => {
    const players = names.map((n) => n.trim());
    onStart({
      players,
      tai: parseFloat(tai) || 0.1,
      yao: parseFloat(yao) || 0.2,
      gang: parseFloat(gang) || 0.2,
      balances: Object.fromEntries(players.map((p) => [p, 0])),
      log: [],
    });
  };

  return (
    <div>
      <h1>Singaporean — new game</h1>
      <h2>Players</h2>
      {names.map((n, i) => (
        <input
          key={i}
          className="text-input"
          placeholder={`Player ${i + 1}`}
          value={n}
          onChange={(e) => setNames((arr) => arr.map((x, j) => (j === i ? e.target.value : x)))}
        />
      ))}
      <h2>Base values</h2>
      <div className="row" style={{ alignItems: "center" }}>
        <label className="vlabel">tai<input className="text-input small" value={tai} onChange={(e) => setTai(e.target.value)} /></label>
        <label className="vlabel">yao (x)<input className="text-input small" value={yao} onChange={(e) => setYao(e.target.value)} /></label>
        <label className="vlabel">gang (y)<input className="text-input small" value={gang} onChange={(e) => setGang(e.target.value)} /></label>
      </div>
      <button className="primary-btn" disabled={!ready} onClick={start}>
        Start game
      </button>
      <button className="link-btn" onClick={onBack}>← Back to menu</button>
    </div>
  );
}

type Action = "hu" | "zimo" | "gang" | "yao";

function Play({ game, setGame, onBack }: { game: SGState; setGame: (s: SGState) => void; onBack: () => void }) {
  const [action, setAction] = useState<Action | null>(null);
  const players = game.players;

  const record = (summary: string, transfers: Transfer[]) => {
    const balances = { ...game.balances };
    applyTransfers(balances, transfers);
    setGame({ ...game, balances, log: [...game.log, { summary, transfers }] });
    setAction(null);
  };

  const endGame = () => {
    if (confirm("End game and clear balances?")) setGame(null as unknown as SGState);
  };

  return (
    <div>
      <h1>Singaporean</h1>

      <h2>Balances</h2>
      <div className="balances">
        {players.map((p) => (
          <div key={p} className="bal-row">
            <span>{p}</span>
            <span className={"bal " + (game.balances[p] >= 0 ? "pos" : "neg")}>
              {game.balances[p] >= 0 ? "+" : ""}
              {game.balances[p].toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      {action === null ? (
        <>
          <h2>Record action</h2>
          <div className="choices">
            <div className="choice-btn" onClick={() => setAction("hu")}>Hu<small>win off discard</small></div>
            <div className="choice-btn" onClick={() => setAction("zimo")}>Zimo<small>self-draw</small></div>
            <div className="choice-btn" onClick={() => setAction("gang")}>Gang<small>kong</small></div>
            <div className="choice-btn" onClick={() => setAction("yao")}>Yao<small>bite</small></div>
          </div>

          {game.log.length > 0 && (
            <>
              <h2>Log</h2>
              <div className="log">
                {game.log.map((e, i) => (
                  <div key={i} className="log-row">{i + 1}. {e.summary}</div>
                ))}
              </div>
            </>
          )}

          <button className="link-btn" onClick={endGame}>End game</button>
          <span style={{ margin: "0 8px" }} />
          <button className="link-btn" onClick={onBack}>← Menu</button>
        </>
      ) : (
        <ActionForm action={action} game={game} onCancel={() => setAction(null)} onConfirm={record} />
      )}
    </div>
  );
}

function ActionForm({
  action,
  game,
  onCancel,
  onConfirm,
}: {
  action: Action;
  game: SGState;
  onCancel: () => void;
  onConfirm: (summary: string, transfers: Transfer[]) => void;
}) {
  const players = game.players;
  const playerOpts = players.map((p) => ({ v: p, label: p }));
  const [s, setS] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setS((prev) => ({ ...prev, [k]: v }));

  let ready = false;
  let build: (() => { summary: string; transfers: Transfer[] }) | null = null;

  if (action === "hu") {
    ready = !!(s.tai && s.winner && s.discarder && s.winner !== s.discarder);
    build = () => {
      const tai = parseInt(s.tai);
      const value = fanToValue(tai, game.tai);
      return { summary: `Hu: ${s.winner} wins off ${s.discarder} (${tai} tai)`, transfers: settleDiscardWin(s.winner, s.discarder, value) };
    };
  } else if (action === "zimo") {
    ready = !!(s.tai && s.winner);
    build = () => {
      const tai = parseInt(s.tai);
      const value = fanToValue(tai, game.tai);
      return { summary: `Zimo: ${s.winner} self-draws (${tai} tai)`, transfers: settleSelfDraw(s.winner, value, players) };
    };
  } else if (action === "gang") {
    ready = !!(s.gtype && s.konger && (s.gtype !== "shoot" || (s.shooter && s.shooter !== s.konger)));
    build = () => {
      const shooter = s.gtype === "shoot" ? s.shooter : null;
      const label = { an: "an gang", shoot: "shoot gang", peng: "gang after peng" }[s.gtype as "an" | "shoot" | "peng"];
      return {
        summary: `Gang: ${s.konger} ${label}${shooter ? ` off ${shooter}` : ""}`,
        transfers: settleGang(s.konger, s.gtype as "an" | "shoot" | "peng", game.gang, players, shooter),
      };
    };
  } else {
    // yao
    ready = !!(s.ytype && s.biter && s.scope && (s.scope !== "one" || (s.target && s.target !== s.biter)));
    build = () => {
      const target = s.scope === "one" ? s.target : null;
      const label = s.ytype === "an" ? "an yao" : "hou yao";
      return {
        summary: `Yao: ${s.biter} ${label}${target ? ` on ${target}` : " on everyone"}`,
        transfers: settleYao(s.biter, s.ytype as "an" | "hou", game.yao, players, target),
      };
    };
  }

  return (
    <div>
      {action === "hu" && (
        <>
          <h2>Tai</h2>
          <Chips options={TAI.map((n) => ({ v: String(n), label: String(n) }))} value={s.tai ?? null} onChange={(v) => set("tai", v)} />
          <h2>Winner</h2>
          <Chips options={playerOpts} value={s.winner ?? null} onChange={(v) => set("winner", v)} />
          <h2>Discarder</h2>
          <Chips options={playerOpts} value={s.discarder ?? null} onChange={(v) => set("discarder", v)} />
        </>
      )}
      {action === "zimo" && (
        <>
          <h2>Winner</h2>
          <Chips options={playerOpts} value={s.winner ?? null} onChange={(v) => set("winner", v)} />
          <h2>Tai</h2>
          <Chips options={TAI.map((n) => ({ v: String(n), label: String(n) }))} value={s.tai ?? null} onChange={(v) => set("tai", v)} />
        </>
      )}
      {action === "gang" && (
        <>
          <h2>Gang type</h2>
          <Chips
            options={[
              { v: "an", label: "An gang (2y)" },
              { v: "shoot", label: "Shoot gang (y)" },
              { v: "peng", label: "After peng (y)" },
            ]}
            value={s.gtype ?? null}
            onChange={(v) => set("gtype", v)}
          />
          <h2>Konger</h2>
          <Chips options={playerOpts} value={s.konger ?? null} onChange={(v) => set("konger", v)} />
          {s.gtype === "shoot" && (
            <>
              <h2>Shooter</h2>
              <Chips options={playerOpts} value={s.shooter ?? null} onChange={(v) => set("shooter", v)} />
            </>
          )}
        </>
      )}
      {action === "yao" && (
        <>
          <h2>Yao type</h2>
          <Chips
            options={[
              { v: "an", label: "An yao (2x)" },
              { v: "hou", label: "Hou yao (x)" },
            ]}
            value={s.ytype ?? null}
            onChange={(v) => set("ytype", v)}
          />
          <h2>Biter</h2>
          <Chips options={playerOpts} value={s.biter ?? null} onChange={(v) => set("biter", v)} />
          <h2>Paid by</h2>
          <Chips
            options={[
              { v: "everyone", label: "Everyone" },
              { v: "one", label: "One person" },
            ]}
            value={s.scope ?? null}
            onChange={(v) => set("scope", v)}
          />
          {s.scope === "one" && (
            <>
              <h2>Who pays</h2>
              <Chips options={playerOpts} value={s.target ?? null} onChange={(v) => set("target", v)} />
            </>
          )}
        </>
      )}

      <button className="primary-btn" disabled={!ready} onClick={() => build && onConfirm(build().summary, build().transfers)}>
        Confirm {action.toUpperCase()}
      </button>
      <button className="link-btn" onClick={onCancel}>← Cancel</button>
    </div>
  );
}
