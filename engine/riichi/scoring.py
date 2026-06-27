"""Riichi (Japanese) mahjong scoring: han + fu -> points and payment splits.

The han/fu -> points math is identical for 3-player (sanma) and 4-player
(yonma) riichi - the only payout difference is how many players pay on a
tsumo (self-draw). That is handled by the ``players`` argument; everything
else (fu, base formula, limit categories, rounding) is shared.

Reference: en.wikipedia.org/wiki/Japanese_mahjong_scoring_rules
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- limit hands --------------------------------------------------------
# Base points for each named limit. A normal hand's base is fu * 2^(2+han),
# capped at 2000 (mangan). 5+ han skips fu and jumps straight to a limit.
MANGAN = 2000
HANEMAN = 3000
BAIMAN = 4000
SANBAIMAN = 6000
YAKUMAN = 8000


def _roundup100(x: float) -> int:
    return int(math.ceil(x / 100.0) * 100)


def base_points(han: int, fu: int, *, kiriage: bool = False, yakuman: int = 0) -> tuple[int, str]:
    """Return (base_points, limit_name) for a hand.

    yakuman > 0 forces a (possibly multiple) yakuman, ignoring han/fu.
    kiriage rounds 4han30fu and 3han60fu up to mangan (a common house rule).
    """
    if yakuman > 0:
        return YAKUMAN * yakuman, ("Yakuman" if yakuman == 1 else f"{yakuman}x Yakuman")
    if han >= 13:
        return YAKUMAN, "Kazoe Yakuman"
    if han >= 11:
        return SANBAIMAN, "Sanbaiman"
    if han >= 8:
        return BAIMAN, "Baiman"
    if han >= 6:
        return HANEMAN, "Haneman"
    if han >= 5:
        return MANGAN, "Mangan"
    if kiriage and ((han == 4 and fu == 30) or (han == 3 and fu == 60)):
        return MANGAN, "Mangan (kiriage)"
    base = fu * (2 ** (2 + han))
    if base >= MANGAN:
        return MANGAN, "Mangan"
    return base, ""


@dataclass
class Payment:
    """`count` players each pay `amount` to the winner, in the given `role`."""

    role: str  # "discarder" | "dealer" | "non-dealer"
    amount: int
    count: int = 1

    @property
    def subtotal(self) -> int:
        return self.amount * self.count


@dataclass
class RiichiScore:
    han: int
    fu: int
    base: int
    limit: str
    dealer: bool
    tsumo: bool
    players: int
    honba: int
    riichi_sticks: int
    payments: list[Payment] = field(default_factory=list)

    @property
    def from_payments(self) -> int:
        return sum(p.subtotal for p in self.payments)

    @property
    def total_gain(self) -> int:
        """Everything the winner collects: payments + honba + riichi sticks."""
        return self.from_payments + self.riichi_sticks * 1000


def score(
    han: int,
    fu: int,
    *,
    dealer: bool,
    tsumo: bool,
    players: int = 4,
    honba: int = 0,
    riichi_sticks: int = 0,
    kiriage: bool = False,
    yakuman: int = 0,
) -> RiichiScore:
    """Full settlement for a riichi winning hand.

    players: 4 (yonma) or 3 (sanma) - only changes the tsumo payer count.
    honba:   each counter adds 300 to a ron, or 100 per payer to a tsumo.
    riichi_sticks: 1000-point bet sticks on the table, all collected by winner.
    """
    if players not in (3, 4):
        raise ValueError("players must be 3 or 4")
    base, limit = base_points(han, fu, kiriage=kiriage, yakuman=yakuman)
    honba_each = 100 * honba  # per-payer honba portion (tsumo)
    payments: list[Payment] = []

    if not tsumo:
        # Ron: the discarder pays the whole value; honba is 300 per counter.
        mult = 6 if dealer else 4
        amount = _roundup100(base * mult) + 300 * honba
        payments.append(Payment("discarder", amount, 1))
    elif dealer:
        # Dealer tsumo: every other player pays 2x base.
        amount = _roundup100(base * 2) + honba_each
        payments.append(Payment("non-dealer", amount, players - 1))
    else:
        # Non-dealer tsumo: dealer pays 2x base, each other non-dealer pays 1x.
        dealer_amt = _roundup100(base * 2) + honba_each
        other_amt = _roundup100(base) + honba_each
        payments.append(Payment("dealer", dealer_amt, 1))
        if players - 2 > 0:
            payments.append(Payment("non-dealer", other_amt, players - 2))

    return RiichiScore(
        han=han,
        fu=fu,
        base=base,
        limit=limit,
        dealer=dealer,
        tsumo=tsumo,
        players=players,
        honba=honba,
        riichi_sticks=riichi_sticks,
        payments=payments,
    )
