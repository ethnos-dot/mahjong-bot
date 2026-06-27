"""Fan-to-value table and payout settlement for SG 4-player mahjong.

Value table reference: doubling per fan, self-draw paid at 2x the discard
rate by each of the other three players (per common SG house-rule apps,
e.g. sgmahjong.club's payout table).
"""
from __future__ import annotations

from dataclasses import dataclass

from .scoring import LIMIT_FAN

SELF_DRAW_MULTIPLIER = 2


def fan_to_value(fan: int, base_unit: float) -> float:
    """Value doubles per fan, starting at 1x base for a chicken hand (fan 0 or 1)."""
    effective_fan = max(fan, 1)
    capped_fan = min(effective_fan, LIMIT_FAN)
    return base_unit * (2 ** (capped_fan - 1))


@dataclass
class Transfer:
    payer: str
    payee: str
    amount: float


def settle_discard_win(winner: str, discarder: str, value: float) -> list[Transfer]:
    """Discarder pays the full value; everyone else pays nothing."""
    return [Transfer(payer=discarder, payee=winner, amount=value)]


def settle_self_draw(winner: str, value: float, players: list[str]) -> list[Transfer]:
    """Self-draw: every other player pays the winner at 2x the discard rate."""
    others = [p for p in players if p != winner]
    amount = value * SELF_DRAW_MULTIPLIER
    return [Transfer(payer=p, payee=winner, amount=amount) for p in others]


def settle_kong_fee(kong_player: str, fee: float, players: list[str]) -> list[Transfer]:
    """Each other player pays a fixed fee to whoever declared a kong."""
    others = [p for p in players if p != kong_player]
    return [Transfer(payer=p, payee=kong_player, amount=fee) for p in others]


def net_balances(transfers: list[Transfer], players: list[str]) -> dict[str, float]:
    balances = {p: 0.0 for p in players}
    for t in transfers:
        balances[t.payer] -= t.amount
        balances[t.payee] += t.amount
    return balances
