// Singaporean mahjong payout settlement, ported from engine/sg/payout.py.
// Each action produces a list of zero-sum transfers (payer -> payee).

export const SELF_DRAW_MULTIPLIER = 2;
export const LIMIT_FAN = 10;

/** Tai value doubles per tai, 1x base for a chicken hand (fan 0 or 1). */
export function fanToValue(fan: number, baseUnit: number): number {
  const eff = Math.max(fan, 1);
  const capped = Math.min(eff, LIMIT_FAN);
  return baseUnit * Math.pow(2, capped - 1);
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

export function settleSelfDraw(winner: string, value: number, players: string[]): Transfer[] {
  return players
    .filter((p) => p !== winner)
    .map((p) => ({ payer: p, payee: winner, amount: value * SELF_DRAW_MULTIPLIER }));
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
