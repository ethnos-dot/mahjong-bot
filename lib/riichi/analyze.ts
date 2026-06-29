// From-tiles riichi analyzer, ported from engine/riichi/analyze.py.
// Pick the 14 tiles + winning tile + context; finds the highest-scoring legal
// interpretation, detects yaku, computes fu, and runs it through score().

import { score, RiichiScore } from "./scoring";

const WINDS = ["EW", "SW", "WW", "NW"];
const DRAGONS = ["RD", "GD", "WD"];
const HONORS = [...WINDS, ...DRAGONS];
const GREEN = new Set(["2B", "3B", "4B", "6B", "8B", "GD"]);

const BASE_FU = 20;
const MENZEN_RON_FU = 10;
const TSUMO_FU = 2;
const YAKUHAI_PAIR_FU = 2;
const OPEN_PINFU_FU = 30;

const isDigit = (ch: string) => ch >= "0" && ch <= "9";
const suit = (c: string): string | null =>
  c.length === 2 && isDigit(c[0]) && "BCD".includes(c[1]) ? c[1] : null;
const rank = (c: string): number | null => (suit(c) ? parseInt(c[0]) : null);
const isTerminal = (c: string) => suit(c) !== null && (rank(c) === 1 || rank(c) === 9);
const isHonor = (c: string) => HONORS.includes(c);
const isTRO = (c: string) => isTerminal(c) || isHonor(c);

export interface CalledMeld {
  kind: "chow" | "pung" | "kan";
  codes: string[];
  concealed?: boolean;
}

export interface WinContext {
  seatWind: string;
  roundWind: string;
  winTile: string;
  tsumo: boolean;
  riichi?: boolean;
  doubleRiichi?: boolean;
  ippatsu?: boolean;
  haitei?: boolean;
  houtei?: boolean;
  rinshan?: boolean;
  chankan?: boolean;
  tenhou?: boolean;
  chiihou?: boolean;
  dora?: number;
  aka?: number;
  ura?: number;
  players?: number;
  honba?: number;
  kiriage?: boolean;
}

interface Meld {
  kind: string; // chow | pung | kan | pair
  codes: string[];
  concealed: boolean;
}
const lead = (m: Meld) => m.codes[0];
const meldIsTRO = (m: Meld) => m.codes.some(isTRO);

export interface AnalyzeResult {
  ok: boolean;
  yaku: [string, number][];
  yakuman: string[];
  han: number;
  fu: number;
  score: RiichiScore | null;
  error: string;
}

type Counter = Map<string, number>;
const counter = (codes: string[]): Counter => {
  const m: Counter = new Map();
  for (const c of codes) m.set(c, (m.get(c) || 0) + 1);
  return m;
};

// All ways to split a multiset into pungs/chows (honor-safe).
function decompose(cnt: Counter): [string, string[]][][] {
  const m: Counter = new Map([...cnt].filter(([, v]) => v > 0));
  if (m.size === 0) return [[]];
  const code = [...m.keys()].sort()[0];
  const results: [string, string[]][][] = [];
  if ((m.get(code) || 0) >= 3) {
    const nxt = new Map(m);
    nxt.set(code, (nxt.get(code) || 0) - 3);
    for (const rest of decompose(nxt)) results.push([["pung", [code, code, code]], ...rest]);
  }
  if (isDigit(code[0]) && "BCD".includes(code[1])) {
    const r = parseInt(code[0]);
    const s = code[1];
    const c2 = `${r + 1}${s}`;
    const c3 = `${r + 2}${s}`;
    if (r <= 7 && (m.get(c2) || 0) > 0 && (m.get(c3) || 0) > 0) {
      const nxt = new Map(m);
      nxt.set(code, (nxt.get(code) || 0) - 1);
      nxt.set(c2, (nxt.get(c2) || 0) - 1);
      nxt.set(c3, (nxt.get(c3) || 0) - 1);
      for (const rest of decompose(nxt)) results.push([["chow", [code, c2, c3]], ...rest]);
    }
  }
  return results;
}

function standardParses(concealed: string[], nMelds: number): [Meld[], string][] {
  const cnt = counter(concealed);
  const out: [Meld[], string][] = [];
  for (const [code, c] of cnt) {
    if (c >= 2) {
      const rest = new Map(cnt);
      rest.set(code, c - 2);
      for (const sets of decompose(rest)) {
        if (sets.length === nMelds) {
          out.push([sets.map(([kind, codes]) => ({ kind, codes, concealed: true })), code]);
        }
      }
    }
  }
  return out;
}

const isChiitoitsu = (codes: string[]) => {
  const c = counter(codes);
  return c.size === 7 && [...c.values()].every((v) => v === 2);
};

const isKokushi = (codes: string[]) => {
  const needed = new Set([...HONORS, ...["B", "C", "D"].flatMap((s) => [`1${s}`, `9${s}`])]);
  const c = counter(codes);
  return c.size === needed.size && [...c.keys()].every((k) => needed.has(k)) && codes.length === 14 && [...c.values()].some((v) => v === 2);
};

function waitType(meld: Meld, winTile: string, isPair: boolean): string {
  if (isPair) return "tanki";
  if (meld.kind === "chow") {
    const b = rank(meld.codes[1]);
    const w = rank(winTile);
    if (w === b) return "kanchan";
    if ((meld.codes[0][0] === "1" && w === 3) || (meld.codes[2][0] === "9" && w === 7)) return "penchan";
    return "ryanmen";
  }
  if (meld.kind === "pung" || meld.kind === "kan") return "shanpon";
  return "ryanmen";
}

function detect(melds: Meld[], pair: Meld, ctx: WinContext, closed: boolean, wait: string): { yaku: [string, number][]; yakuman: string[] } {
  const yaku: [string, number][] = [];
  const yakuman: string[] = [];
  const add = (n: string, h: number) => yaku.push([n, h]);
  const allSets = [...melds, pair];
  const allCodes = allSets.flatMap((m) => m.codes);
  const chows = melds.filter((m) => m.kind === "chow");
  const pungs = melds.filter((m) => m.kind === "pung" || m.kind === "kan");
  const suits = new Set(allCodes.map(suit).filter((s): s is string => s !== null));
  const hasHonor = allCodes.some(isHonor);

  if (ctx.riichi && !ctx.doubleRiichi) add("Riichi", 1);
  if (ctx.doubleRiichi) add("Double Riichi", 2);
  if (ctx.ippatsu) add("Ippatsu", 1);
  if (closed && ctx.tsumo) add("Menzen Tsumo", 1);
  if (ctx.haitei) add("Haitei", 1);
  if (ctx.houtei) add("Houtei", 1);
  if (ctx.rinshan) add("Rinshan", 1);
  if (ctx.chankan) add("Chankan", 1);

  for (const m of pungs) {
    if (DRAGONS.includes(lead(m))) add(`Yakuhai (${lead(m)})`, 1);
    else if (lead(m) === ctx.seatWind) add("Yakuhai (seat wind)", 1);
    else if (lead(m) === ctx.roundWind) add("Yakuhai (round wind)", 1);
    if (lead(m) === ctx.seatWind && lead(m) === ctx.roundWind) add("Yakuhai (double wind)", 1);
  }

  if (!allCodes.some(isTRO)) add("Tanyao", 1);

  const pairYakuhai = DRAGONS.includes(lead(pair)) || lead(pair) === ctx.seatWind || lead(pair) === ctx.roundWind;
  if (closed && chows.length === 4 && !pairYakuhai && wait === "ryanmen") add("Pinfu", 1);

  if (closed) {
    const chowKeys = new Map<string, number>();
    for (const m of chows) chowKeys.set(m.codes.join(","), (chowKeys.get(m.codes.join(",")) || 0) + 1);
    const dups = [...chowKeys.values()].reduce((s, v) => s + Math.floor(v / 2), 0);
    if (dups === 2) add("Ryanpeikou", 3);
    else if (dups === 1) add("Iipeikou", 1);
  }

  const chowSet = new Set(chows.map((m) => m.codes.join(",")));
  for (let start = 1; start <= 7; start++) {
    if (["B", "C", "D"].every((s) => chowSet.has([`${start}${s}`, `${start + 1}${s}`, `${start + 2}${s}`].join(",")))) {
      add("Sanshoku", closed ? 2 : 1);
      break;
    }
  }

  const pungRanks = new Map<number, Set<string>>();
  for (const m of pungs) {
    const s = suit(lead(m));
    const r = rank(lead(m));
    if (s !== null && r !== null) {
      if (!pungRanks.has(r)) pungRanks.set(r, new Set());
      pungRanks.get(r)!.add(s);
    }
  }
  if ([...pungRanks.values()].some((s) => s.size === 3)) add("Sanshoku Doukou", 2);

  for (const s of ["B", "C", "D"]) {
    const need = [[`1${s}`, `2${s}`, `3${s}`], [`4${s}`, `5${s}`, `6${s}`], [`7${s}`, `8${s}`, `9${s}`]];
    if (need.every((n) => chowSet.has(n.join(",")))) {
      add("Ittsuu", closed ? 2 : 1);
      break;
    }
  }

  if (allSets.every(meldIsTRO) && chows.length > 0) {
    if (hasHonor) add("Chanta", closed ? 2 : 1);
    else add("Junchan", closed ? 3 : 2);
  }

  if (pungs.length === 4) add("Toitoi", 2);
  const concealedTriplets = pungs.filter((m) => m.concealed);
  if (concealedTriplets.length === 3) add("Sanankou", 2);
  if (pungs.filter((m) => m.kind === "kan").length === 3) add("Sankantsu", 2);

  if (allCodes.every(isTRO) && chows.length === 0) add("Honroutou", 2);

  const dragonPungs = pungs.filter((m) => DRAGONS.includes(lead(m)));
  if (dragonPungs.length === 2 && DRAGONS.includes(lead(pair))) add("Shousangen", 2);

  if (suits.size === 1 && !hasHonor) add("Chinitsu", closed ? 6 : 5);
  else if (suits.size === 1 && hasHonor) add("Honitsu", closed ? 3 : 2);

  // yakuman
  if (dragonPungs.length === 3) yakuman.push("Daisangen");
  const windPungs = pungs.filter((m) => WINDS.includes(lead(m)));
  if (windPungs.length === 4) yakuman.push("Daisuushii");
  else if (windPungs.length === 3 && WINDS.includes(lead(pair))) yakuman.push("Shousuushii");
  if (allCodes.every(isHonor)) yakuman.push("Tsuuiisou");
  if (allCodes.every(isTerminal)) yakuman.push("Chinroutou");
  if (allCodes.every((c) => GREEN.has(c))) yakuman.push("Ryuuiisou");
  if (pungs.filter((m) => m.kind === "kan").length === 4) yakuman.push("Suukantsu");
  if (concealedTriplets.length === 4) yakuman.push("Suuankou");
  if (ctx.tenhou) yakuman.push("Tenhou");
  if (ctx.chiihou) yakuman.push("Chiihou");

  return { yaku, yakuman };
}

const hanFromYaku = (yaku: [string, number][]) => yaku.reduce((s, [, h]) => s + h, 0);

function computeFu(melds: Meld[], pair: Meld, ctx: WinContext, closed: boolean, wait: string, pinfu = false): number {
  if (pinfu) return ctx.tsumo ? 20 : 30;
  let fu = BASE_FU;
  if (closed && !ctx.tsumo) fu += MENZEN_RON_FU;
  if (ctx.tsumo) fu += TSUMO_FU;
  if (wait === "kanchan" || wait === "penchan" || wait === "tanki") fu += 2;
  if (DRAGONS.includes(lead(pair)) || lead(pair) === ctx.seatWind || lead(pair) === ctx.roundWind) fu += YAKUHAI_PAIR_FU;
  for (const m of melds) {
    if (m.kind === "chow") continue;
    const tro = meldIsTRO(m);
    const base = m.kind === "kan" ? (m.concealed ? 16 : 8) : m.concealed ? 4 : 2;
    fu += base * (tro ? 2 : 1);
  }
  const rounded = Math.ceil(fu / 10) * 10;
  if (!closed && rounded === BASE_FU) return OPEN_PINFU_FU;
  return rounded;
}

const dealerOf = (ctx: WinContext) => ctx.seatWind === "EW";

function scoreCandidate(yaku: [string, number][], yakuman: string[], fu: number, ctx: WinContext): AnalyzeResult {
  const dealer = dealerOf(ctx);
  const players = ctx.players ?? 4;
  const honba = ctx.honba ?? 0;
  if (yakuman.length > 0) {
    const s = score(0, 0, { dealer, tsumo: ctx.tsumo, players, honba, yakuman: yakuman.length });
    return { ok: true, yaku: yaku.filter(([n]) => n !== "__").map(([n]) => [n, 0] as [string, number]), yakuman, han: 0, fu: 0, score: s, error: "" };
  }
  const dora = (ctx.dora ?? 0) + (ctx.aka ?? 0) + (ctx.ura ?? 0);
  const han = hanFromYaku(yaku) + dora;
  const s = score(han, fu, { dealer, tsumo: ctx.tsumo, players, honba, kiriage: ctx.kiriage });
  const yk = [...yaku];
  if (ctx.dora) yk.push(["Dora", ctx.dora]);
  if (ctx.aka) yk.push(["Aka dora", ctx.aka]);
  if (ctx.ura) yk.push(["Ura dora", ctx.ura]);
  return { ok: true, yaku: yk, yakuman: [], han, fu, score: s, error: "" };
}

function chiitoitsuCandidate(fullCodes: string[], ctx: WinContext): AnalyzeResult {
  const yaku: [string, number][] = [["Chiitoitsu", 2]];
  if (ctx.riichi && !ctx.doubleRiichi) yaku.push(["Riichi", 1]);
  if (ctx.doubleRiichi) yaku.push(["Double Riichi", 2]);
  if (ctx.ippatsu) yaku.push(["Ippatsu", 1]);
  if (ctx.tsumo) yaku.push(["Menzen Tsumo", 1]);
  if (ctx.haitei) yaku.push(["Haitei", 1]);
  if (ctx.houtei) yaku.push(["Houtei", 1]);
  const suits = new Set(fullCodes.map(suit).filter((s): s is string => s !== null));
  const hasHonor = fullCodes.some(isHonor);
  if (!fullCodes.some(isTRO)) yaku.push(["Tanyao", 1]);
  if (suits.size === 1 && !hasHonor) yaku.push(["Chinitsu", 6]);
  else if (suits.size === 1 && hasHonor) yaku.push(["Honitsu", 3]);
  return scoreCandidate(yaku, [], 25, ctx);
}

function winAssignments(melds: Meld[], pair: Meld, ctx: WinContext): [Meld[], Meld, string][] {
  const w = ctx.winTile;
  const out: [Meld[], Meld, string][] = [];
  let seen = false;
  if (lead(pair) === w) {
    out.push([melds, pair, "tanki"]);
    seen = true;
  }
  melds.forEach((m, i) => {
    if (m.codes.includes(w)) {
      const wait = waitType(m, w, false);
      const adj = [...melds];
      if (m.kind === "pung" && !ctx.tsumo) adj[i] = { ...m, concealed: false };
      out.push([adj, pair, wait]);
      seen = true;
    }
  });
  if (!seen) out.push([melds, pair, "ryanmen"]);
  return out;
}

const better = (a: AnalyzeResult, b: AnalyzeResult) => (a.score?.total ?? 0) > (b.score?.total ?? 0);

export function analyze(concealed: string[], called: CalledMeld[], ctx: WinContext): AnalyzeResult {
  called = called || [];
  const calledMelds: Meld[] = called.map((m) => ({ kind: m.kind, codes: m.codes, concealed: m.concealed ?? false }));
  const fullCodes = [...concealed, ...called.flatMap((m) => m.codes.slice(0, 3))];
  const closed = calledMelds.every((m) => m.concealed);

  if (called.length === 0 && isKokushi(fullCodes)) return scoreCandidate([], ["Kokushi Musou"], 0, ctx);

  const candidates: AnalyzeResult[] = [];
  if (called.length === 0 && isChiitoitsu(fullCodes)) candidates.push(chiitoitsuCandidate(fullCodes, ctx));

  const nMelds = 4 - calledMelds.length;
  const parses = standardParses([...concealed], nMelds);
  if (parses.length === 0 && candidates.length === 0) {
    return { ok: false, yaku: [], yakuman: [], han: 0, fu: 0, score: null, error: "not a valid winning hand" };
  }

  let best: AnalyzeResult | null = null;
  for (const cand of candidates) if (cand.ok && (best === null || better(cand, best))) best = cand;

  for (const [parseMelds, pairCode] of parses) {
    const melds = [...calledMelds, ...parseMelds];
    const pair: Meld = { kind: "pair", codes: [pairCode, pairCode], concealed: true };
    for (const [aMelds, aPair, wait] of winAssignments(melds, pair, ctx)) {
      const { yaku, yakuman } = detect(aMelds, aPair, ctx, closed, wait);
      if (yakuman.length === 0 && hanFromYaku(yaku) === 0) continue;
      const isPinfu = yaku.some(([n]) => n === "Pinfu");
      const fu = computeFu(aMelds, aPair, ctx, closed, wait, isPinfu);
      const cand = scoreCandidate(yaku, yakuman, fu, ctx);
      if (best === null || better(cand, best)) best = cand;
    }
  }

  if (best === null) return { ok: false, yaku: [], yakuman: [], han: 0, fu: 0, score: null, error: "no yaku (hand has no scoring element)" };
  return best;
}
