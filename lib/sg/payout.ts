// Singaporean mahjong payout settlement, ported from engine/sg/payout.py.
// Each action produces a list of zero-sum transfers (payer -> payee).
//
// Payouts are configurable per game/session via PayoutConfig so the values can
// be set to match any house table (e.g. sgmahjong.club). Old games stored just
// { tai, yao, gang }; everything else falls back to the original house rules.

export const LIMIT_TAI = 10;

export interface PayoutConfig {
  /** Discard (shooter) win value at 1 tai; doubles each tai up to `cap`. */
  tai: number;
  /** Self-draw: amount EACH other player pays at 1 tai (doubles each tai).
   *  Defaults to 2× the discard value (the original house rule). */
  zimo?: number;
  /** Bite (yao) base value x. */
  yao: number;
  /** Kong (gang) base value y. */
  gang: number;
  /** Highest selectable tai (default 10). */
  maxTai?: number;
  /** Doubling cap — at/above this tai the value stops doubling (default maxTai). */
  cap?: number;
  /** Optional exact per-tai discard amounts (index = tai-1); overrides doubling. */
  discardTable?: (number | null)[];
  /** Optional exact per-tai self-draw-each amounts (index = tai-1). */
  zimoTable?: (number | null)[];
}

/** The original defaults: 0.10 tai, 0.20 yao/gang, self-draw = 2×, doubling to 10. */
export const DEFAULT_PAYOUT: PayoutConfig = { tai: 0.1, yao: 0.2, gang: 0.2 };

export const maxTaiOf = (c: PayoutConfig): number => c.maxTai ?? LIMIT_TAI;
export const capOf = (c: PayoutConfig): number => c.cap ?? maxTaiOf(c);
/** Self-draw 1-tai base; defaults to twice the discard base (house rule). */
export const zimoBaseOf = (c: PayoutConfig): number => (c.zimo ?? c.tai * 2);

function doubleFrom(base: number, tai: number, cap: number): number {
  const t = Math.min(Math.max(tai, 1), Math.max(cap, 1));
  return base * Math.pow(2, t - 1);
}

/** What a single discarder (shooter) pays the winner at `tai`. */
export function discardValue(c: PayoutConfig, tai: number): number {
  const exact = c.discardTable?.[tai - 1];
  if (exact != null) return exact;
  return doubleFrom(c.tai, tai, capOf(c));
}

/** What EACH other player pays the winner on a self-draw at `tai`. */
export function zimoEachValue(c: PayoutConfig, tai: number): number {
  const exact = c.zimoTable?.[tai - 1];
  if (exact != null) return exact;
  return doubleFrom(zimoBaseOf(c), tai, capOf(c));
}

export interface Transfer {
  payer: string;
  payee: string;
  amount: number;
}

const splitEqually = (payee: string, total: number, payers: string[]): Transfer[] =>
  payers.map((p) => ({ payer: p, payee, amount: total / payers.length }));

export function settleDiscardWin(winner: string, discarder: string, value: number): Transfer[] {
  return [{ payer: discarder, payee: winner, amount: value }];
}

/** Self-draw: each other player pays `perPlayer` to the winner. */
export function settleSelfDraw(winner: string, perPlayer: number, players: string[]): Transfer[] {
  return players
    .filter((p) => p !== winner)
    .map((p) => ({ payer: p, payee: winner, amount: perPlayer }));
}

// Yao (bite): an = 2x, hou = x. Everyone splits, or one target pays it all.
const YAO_MULTIPLIER: Record<string, number> = { an: 2, hou: 1 };
export function settleYao(
  biter: string,
  yaoType: "an" | "hou",
  x: number,
  players: string[],
  target?: string | null,
): Transfer[] {
  const total = YAO_MULTIPLIER[yaoType] * x;
  if (target) return [{ payer: target, payee: biter, amount: total }];
  return splitEqually(biter, total, players.filter((p) => p !== biter));
}

// Gang (kong): an = 2y (split 3); shoot = y (shooter pays alone, else split);
// peng = y (split 3).
const GANG_MULTIPLIER: Record<string, number> = { an: 2, shoot: 1, peng: 1 };
export function settleGang(
  konger: string,
  gangType: "an" | "shoot" | "peng",
  y: number,
  players: string[],
  shooter?: string | null,
): Transfer[] {
  const total = GANG_MULTIPLIER[gangType] * y;
  if (gangType === "shoot" && shooter) return [{ payer: shooter, payee: konger, amount: total }];
  return splitEqually(konger, total, players.filter((p) => p !== konger));
}

export function applyTransfers(balances: Record<string, number>, transfers: Transfer[]): void {
  for (const t of transfers) {
    balances[t.payer] = (balances[t.payer] || 0) - t.amount;
    balances[t.payee] = (balances[t.payee] || 0) + t.amount;
  }
}
