"""Decomposes 14 playing tiles into 4 sets + 1 pair (all valid interpretations)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .tiles import Tile

SetKind = str  # "chow" | "pung" | "kong" | "pair"


@dataclass(frozen=True)
class TileSet:
    kind: SetKind
    tiles: tuple[Tile, ...]


def _counter_to_tiles(counter: Counter) -> list[Tile]:
    tiles: list[Tile] = []
    for code, n in counter.items():
        tiles.extend([Tile(code)] * n)
    return tiles


def _decompose_sets(counter: Counter) -> list[list[TileSet]]:
    """Recursively decompose a multiset of tiles into pungs/chows only (no pair)."""
    if not counter:
        return [[]]

    counter = Counter({k: v for k, v in counter.items() if v > 0})
    if not counter:
        return [[]]

    code = min(counter, key=lambda c: (c[1] if len(c) == 2 and c[1] in "BCD" else "", c))
    results: list[list[TileSet]] = []

    # Try pung (triplet)
    if counter[code] >= 3:
        nxt = counter.copy()
        nxt[code] -= 3
        for rest in _decompose_sets(nxt):
            results.append([TileSet("pung", (Tile(code),) * 3)] + rest)

    # Try chow (sequence) - only for suited tiles
    if len(code) == 2 and code[1] in "BCD":
        rank, suit = int(code[0]), code[1]
        c2, c3 = f"{rank + 1}{suit}", f"{rank + 2}{suit}"
        if rank <= 7 and counter.get(c2, 0) > 0 and counter.get(c3, 0) > 0:
            nxt = counter.copy()
            nxt[code] -= 1
            nxt[c2] -= 1
            nxt[c3] -= 1
            for rest in _decompose_sets(nxt):
                results.append([TileSet("chow", (Tile(code), Tile(c2), Tile(c3)))] + rest)

    return results


def find_decompositions(playing_tiles: list[Tile]) -> list[list[TileSet]]:
    """Returns every valid way to split 14 tiles into 4 sets + 1 pair."""
    counter = Counter(t.code for t in playing_tiles)
    if sum(counter.values()) != 14:
        return []

    decompositions: list[list[TileSet]] = []
    for code, n in list(counter.items()):
        if n >= 2:
            nxt = counter.copy()
            nxt[code] -= 2
            for sets in _decompose_sets(nxt):
                if len(sets) == 4:
                    decompositions.append([TileSet("pair", (Tile(code), Tile(code)))] + sets)
    return decompositions


def is_seven_pairs(playing_tiles: list[Tile]) -> bool:
    counter = Counter(t.code for t in playing_tiles)
    return len(counter) == 7 and all(n == 2 for n in counter.values())
