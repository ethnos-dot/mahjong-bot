"""Riichi yaku reference: han values for every yaku, plus yakuman.

This is reference data, not a from-tiles detector. A UI (or the bot) lets the
player pick which yaku their hand has; `total_han` sums them, accounting for
the open-hand han reduction ("kuisagari") and closed-only yaku. Dora are added
on top as flat han.

Reference: en.wikipedia.org/wiki/Japanese_mahjong_yaku
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Yaku:
    key: str
    name: str            # romaji
    en: str              # english
    closed_han: int      # han when hand is closed
    open_han: int | None  # han when open; None = cannot be open (closed-only)

    @property
    def closed_only(self) -> bool:
        return self.open_han is None


# --- standard yaku (1-6 han) -------------------------------------------
YAKU: list[Yaku] = [
    # 1 han
    Yaku("riichi", "Riichi", "Riichi declaration", 1, None),
    Yaku("ippatsu", "Ippatsu", "One-shot (within a turn of riichi)", 1, None),
    Yaku("menzen_tsumo", "Menzen Tsumo", "Closed self-draw", 1, None),
    Yaku("pinfu", "Pinfu", "All-sequences no-fu hand", 1, None),
    Yaku("iipeikou", "Iipeikou", "One set of identical sequences", 1, None),
    Yaku("tanyao", "Tanyao", "All simples", 1, 1),
    Yaku("yakuhai", "Yakuhai", "Dragon / seat / round wind triplet (per triplet)", 1, 1),
    Yaku("haitei", "Haitei", "Win on the last tile (tsumo)", 1, 1),
    Yaku("houtei", "Houtei", "Win on the last discard (ron)", 1, 1),
    Yaku("rinshan", "Rinshan Kaihou", "Win on the dead-wall replacement tile", 1, 1),
    Yaku("chankan", "Chankan", "Robbing a kan", 1, 1),
    # 2 han
    Yaku("double_riichi", "Double Riichi", "Riichi on the first discard", 2, None),
    Yaku("chiitoitsu", "Chiitoitsu", "Seven pairs", 2, None),
    Yaku("sanshoku", "Sanshoku Doujun", "Three-colour straight (same sequence)", 2, 1),
    Yaku("ittsuu", "Ittsuu", "Pure straight 1-9 in one suit", 2, 1),
    Yaku("chanta", "Chanta", "Terminal/honor in every set", 2, 1),
    Yaku("toitoi", "Toitoi", "All triplets", 2, 2),
    Yaku("sanankou", "San Ankou", "Three concealed triplets", 2, 2),
    Yaku("sanshoku_doukou", "Sanshoku Doukou", "Three-colour triplets", 2, 2),
    Yaku("sankantsu", "San Kantsu", "Three quads", 2, 2),
    Yaku("honroutou", "Honroutou", "All terminals and honors", 2, 2),
    Yaku("shousangen", "Shousangen", "Little three dragons", 2, 2),
    # 3 han
    Yaku("honitsu", "Honitsu", "Half flush (one suit + honors)", 3, 2),
    Yaku("junchan", "Junchan", "Terminal in every set (no honors)", 3, 2),
    Yaku("ryanpeikou", "Ryanpeikou", "Two sets of identical sequences", 3, None),
    # 6 han
    Yaku("chinitsu", "Chinitsu", "Full flush (one suit only)", 6, 5),
    # mangan-fixed special
    Yaku("nagashi_mangan", "Nagashi Mangan", "All-terminal/honor discards, exhaustive draw", 5, 5),
]

YAKU_BY_KEY = {y.key: y for y in YAKU}


# --- yakuman (limit hands) ---------------------------------------------
@dataclass(frozen=True)
class Yakuman:
    key: str
    name: str
    en: str
    multiplier: int  # 1 = single yakuman, 2 = double yakuman


YAKUMAN: list[Yakuman] = [
    Yakuman("kokushi", "Kokushi Musou", "Thirteen orphans", 1),
    Yakuman("kokushi_13", "Kokushi 13-men", "Thirteen orphans, 13-sided wait", 2),
    Yakuman("suuankou", "Suu Ankou", "Four concealed triplets", 1),
    Yakuman("suuankou_tanki", "Suu Ankou Tanki", "Four concealed triplets, pair wait", 2),
    Yakuman("daisangen", "Daisangen", "Big three dragons", 1),
    Yakuman("shousuushii", "Shousuushii", "Little four winds", 1),
    Yakuman("daisuushii", "Daisuushii", "Big four winds", 2),
    Yakuman("tsuuiisou", "Tsuuiisou", "All honors", 1),
    Yakuman("chinroutou", "Chinroutou", "All terminals", 1),
    Yakuman("ryuuiisou", "Ryuuiisou", "All green", 1),
    Yakuman("suukantsu", "Suu Kantsu", "Four quads", 1),
    Yakuman("chuuren", "Chuuren Poutou", "Nine gates", 1),
    Yakuman("chuuren_pure", "Junsei Chuuren", "Pure nine gates (9-sided wait)", 2),
    Yakuman("tenhou", "Tenhou", "Blessing of heaven (dealer)", 1),
    Yakuman("chiihou", "Chiihou", "Blessing of earth (non-dealer)", 1),
]

YAKUMAN_BY_KEY = {y.key: y for y in YAKUMAN}


def total_han(yaku_keys: list[str], *, closed: bool, dora: int = 0) -> int:
    """Sum han for the chosen yaku at the right open/closed value, plus dora.

    Raises ValueError if an open hand claims a closed-only yaku.
    """
    han = 0
    for key in yaku_keys:
        y = YAKU_BY_KEY[key]
        if closed:
            han += y.closed_han
        else:
            if y.closed_only:
                raise ValueError(f"{y.name} is closed-only and cannot be claimed on an open hand")
            han += y.open_han
    return han + dora


def total_yakuman(yakuman_keys: list[str]) -> int:
    """Sum the yakuman multiplier (1 per single, 2 per double) for the picks."""
    return sum(YAKUMAN_BY_KEY[k].multiplier for k in yakuman_keys)
