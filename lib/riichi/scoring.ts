// Riichi scoring: han + fu -> base points and role-based payment split.
// Ported from the Python engine (engine/riichi/scoring.py). Identical math for
// 3-player (sanma) and 4-player (yonma) - only the tsumo payer count differs.

export const MANGAN = 2000;
export const HANEMAN = 3000;
export const BAIMAN = 4000;
export const SANBAIMAN = 6000;
export const YAKUMAN = 8000;

const roundup100 = (x: number) => Math.ceil(x / 100) * 100;

export function basePoints(
  han: number,
  fu: number,
  opts: { kiriage?: boolean; yakuman?: number } = {},
): { base: number; limit: string } {
  const { kiriage = false, yakuman = 0 } = opts;
  if (yakuman > 0) return { base: YAKUMAN * yakuman, limit: yakuman === 1 ? "Yakuman" : `${yakuman}× Yakuman` };
  if (han >= 13) return { base: YAKUMAN, limit: "Kazoe Yakuman" };
  if (han >= 11) return { base: SANBAIMAN, limit: "Sanbaiman" };
  if (han >= 8) return { base: BAIMAN, limit: "Baiman" };
  if (han >= 6) return { base: HANEMAN, limit: "Haneman" };
  if (han >= 5) return { base: MANGAN, limit: "Mangan" };
  if (kiriage && ((han === 4 && fu === 30) || (han === 3 && fu === 60)))
    return { base: MANGAN, limit: "Mangan (kiriage)" };
  const base = fu * Math.pow(2, 2 + han);
  if (base >= MANGAN) return { base: MANGAN, limit: "Mangan" };
  return { base, limit: "" };
}

export type PaymentRole = "discarder" | "dealer" | "non-dealer";

export interface Payment {
  role: PaymentRole;
  amount: number;
  count: number;
}

export interface RiichiScore {
  han: number;
  fu: number;
  base: number;
  limit: string;
  dealer: boolean;
  tsumo: boolean;
  players: number;
  honba: number;
  payments: Payment[];
  total: number;
}

export function score(
  han: number,
  fu: number,
  opts: {
    dealer: boolean;
    tsumo: boolean;
    players?: number;
    honba?: number;
    kiriage?: boolean;
    yakuman?: number;
  },
): RiichiScore {
  const { dealer, tsumo, players = 4, honba = 0, kiriage = false, yakuman = 0 } = opts;
  const { base, limit } = basePoints(han, fu, { kiriage, yakuman });
  const honbaEach = 100 * honba;
  const payments: Payment[] = [];

  if (!tsumo) {
    const mult = dealer ? 6 : 4;
    payments.push({ role: "discarder", amount: roundup100(base * mult) + 300 * honba, count: 1 });
  } else if (dealer) {
    payments.push({ role: "non-dealer", amount: roundup100(base * 2) + honbaEach, count: players - 1 });
  } else {
    payments.push({ role: "dealer", amount: roundup100(base * 2) + honbaEach, count: 1 });
    if (players - 2 > 0)
      payments.push({ role: "non-dealer", amount: roundup100(base) + honbaEach, count: players - 2 });
  }

  const total = payments.reduce((s, p) => s + p.amount * p.count, 0);
  return { han, fu, base, limit, dealer, tsumo, players, honba, payments, total };
}
