"""Fu (符) calculation for riichi mahjong.

Fu is the minor component of a hand's value (the other being han). It is
summed from the sources below then rounded UP to the next 10. Two hands
ignore this entirely: seven pairs is always 25 fu, and pinfu is fixed
(20 on tsumo, 30 on a closed ron).

Reference: en.wikipedia.org/wiki/Japanese_mahjong_scoring_rules
"""
from __future__ import annotations

from dataclasses import dataclass, field

BASE_FU = 20
MENZEN_RON_FU = 10  # closed hand won by ron
TSUMO_FU = 2  # self-draw (except pinfu)
YAKUHAI_PAIR_FU = 2  # pair of dragons / round wind / seat wind
CHIITOITSU_FU = 25
PINFU_TSUMO_FU = 20
PINFU_RON_FU = 30
OPEN_PINFU_FU = 30  # open hand that otherwise totals 20 fu is bumped to 30

# Wait fu: two-sided (ryanmen) and triplet (shanpon) waits give 0;
# closed/edge/pair waits give 2.
WAIT_FU = {"ryanmen": 0, "shanpon": 0, "kanchan": 2, "penchan": 2, "tanki": 2}

# Triplet / quad fu: (kind, terminal_or_honor) -> fu
TRIPLET_FU = {
    ("open_pung", False): 2,  # minko, simples
    ("open_pung", True): 4,   # minko, terminals/honors
    ("closed_pung", False): 4,  # anko, simples
    ("closed_pung", True): 8,   # anko, terminals/honors
    ("open_kan", False): 8,   # minkan, simples
    ("open_kan", True): 16,   # minkan, terminals/honors
    ("closed_kan", False): 16,  # ankan, simples
    ("closed_kan", True): 32,   # ankan, terminals/honors
}


def _roundup10(x: int) -> int:
    return -(-x // 10) * 10


@dataclass
class Meld:
    kind: str  # one of TRIPLET_FU's first key, or "chow" (0 fu)
    terminal_or_honor: bool = False

    @property
    def fu(self) -> int:
        if self.kind == "chow":
            return 0
        return TRIPLET_FU[(self.kind, self.terminal_or_honor)]


@dataclass
class FuHand:
    """Components of a standard (4 melds + pair) hand for fu counting."""

    closed: bool          # menzen (no called melds)
    tsumo: bool
    wait: str = "ryanmen"  # see WAIT_FU
    yakuhai_pair: bool = False
    melds: list[Meld] = field(default_factory=list)
    pinfu: bool = False
    chiitoitsu: bool = False


def calc_fu(hand: FuHand) -> int:
    """Total fu for a hand, rounded up to the next 10 (with the fixed-value
    special cases applied first)."""
    if hand.chiitoitsu:
        return CHIITOITSU_FU
    if hand.pinfu:
        return PINFU_TSUMO_FU if hand.tsumo else PINFU_RON_FU

    fu = BASE_FU
    if hand.closed and not hand.tsumo:
        fu += MENZEN_RON_FU
    if hand.tsumo:
        fu += TSUMO_FU
    fu += WAIT_FU.get(hand.wait, 0)
    if hand.yakuhai_pair:
        fu += YAKUHAI_PAIR_FU
    for m in hand.melds:
        fu += m.fu

    rounded = _roundup10(fu)
    # Open hand with no fu sources (kuipinfu) is counted as 30, not 20.
    if not hand.closed and rounded == BASE_FU:
        return OPEN_PINFU_FU
    return rounded
