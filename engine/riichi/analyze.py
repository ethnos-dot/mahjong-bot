"""From-tiles riichi analyzer: tiles + win context -> yaku, fu, han, payout.

Pick the 14 tiles (concealed part + any called melds) and the winning tile,
set the win context (ron/tsumo, winds, riichi/dora flags), and this finds the
highest-scoring legal interpretation of the hand, detects its yaku, computes
fu, and runs it through scoring.score().

Tile codes (shared with engine.tiles): suited "<1-9><B|C|D>" where B=bamboo
(sou), C=character/man, D=dot/pin; winds EW/SW/WW/NW; dragons RD/GD/WD.

Scope: standard 4-meld hands, seven pairs, thirteen orphans, and the common
yaku/yakuman. Exotic combinations and rare fu edge cases may be incomplete;
the manual yaku.total_han + scoring.score path remains the fallback.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from . import scoring
from .fu import (
    BASE_FU,
    MENZEN_RON_FU,
    OPEN_PINFU_FU,
    TSUMO_FU,
    YAKUHAI_PAIR_FU,
)

WINDS = ("EW", "SW", "WW", "NW")
DRAGONS = ("RD", "GD", "WD")
HONORS = WINDS + DRAGONS
GREEN = {"2B", "3B", "4B", "6B", "8B", "GD"}


def _suit(code: str) -> str | None:
    # Suited tiles are "<digit><B|C|D>"; honors like WD/RD/GD also end in a
    # letter, so require a leading digit to avoid mis-reading them as dots.
    return code[1] if len(code) == 2 and code[0].isdigit() and code[1] in "BCD" else None


def _rank(code: str) -> int | None:
    return int(code[0]) if _suit(code) else None


def _is_terminal(code: str) -> bool:
    return _suit(code) is not None and _rank(code) in (1, 9)


def _is_honor(code: str) -> bool:
    return code in HONORS


def _is_tro(code: str) -> bool:  # terminal or honor
    return _is_terminal(code) or _is_honor(code)


# --- input structures ---------------------------------------------------

@dataclass
class CalledMeld:
    kind: str            # "chow" | "pung" | "kan"
    codes: tuple[str, ...]
    concealed: bool = False  # True only for an ankan (concealed kan)


@dataclass
class WinContext:
    seat_wind: str
    round_wind: str
    win_tile: str
    tsumo: bool
    riichi: bool = False
    double_riichi: bool = False
    ippatsu: bool = False
    haitei: bool = False    # last tile (tsumo) / houtei = last discard (ron)
    houtei: bool = False
    rinshan: bool = False
    chankan: bool = False
    tenhou: bool = False
    chiihou: bool = False
    dora: int = 0
    aka: int = 0
    ura: int = 0
    players: int = 4
    honba: int = 0
    riichi_sticks: int = 0
    kiriage: bool = False


@dataclass
class Meld:
    kind: str            # chow | pung | kan | pair
    codes: tuple[str, ...]
    concealed: bool

    @property
    def lead(self) -> str:
        return self.codes[0]

    @property
    def is_tro(self) -> bool:
        return any(_is_tro(c) for c in self.codes)


@dataclass
class AnalyzeResult:
    ok: bool
    yaku: list[tuple[str, int]] = field(default_factory=list)  # (name, han)
    yakuman: list[str] = field(default_factory=list)
    han: int = 0
    fu: int = 0
    score: scoring.RiichiScore | None = None
    error: str = ""


# --- decomposition ------------------------------------------------------

def _decompose(counter: Counter) -> list[list[tuple[str, tuple[str, ...]]]]:
    """All ways to split a tile multiset into pungs/chows. Honor-safe: honors
    (which end in a letter) only ever form pungs, never chows."""
    counter = Counter({k: v for k, v in counter.items() if v > 0})
    if not counter:
        return [[]]
    code = sorted(counter)[0]  # smallest tile; chows only extend upward
    results: list[list[tuple[str, tuple[str, ...]]]] = []
    if counter[code] >= 3:
        nxt = counter.copy()
        nxt[code] -= 3
        for rest in _decompose(nxt):
            results.append([("pung", (code,) * 3)] + rest)
    if code[0].isdigit() and code[1] in "BCD":
        r, s = int(code[0]), code[1]
        c2, c3 = f"{r + 1}{s}", f"{r + 2}{s}"
        if r <= 7 and counter.get(c2, 0) > 0 and counter.get(c3, 0) > 0:
            nxt = counter.copy()
            nxt[code] -= 1
            nxt[c2] -= 1
            nxt[c3] -= 1
            for rest in _decompose(nxt):
                results.append([("chow", (code, c2, c3))] + rest)
    return results


def _standard_parses(concealed: list[str], n_melds: int):
    """All (melds, pair_code) splitting concealed tiles into n_melds + a pair."""
    counter = Counter(concealed)
    out = []
    for code, cnt in list(counter.items()):
        if cnt >= 2:
            rest = counter.copy()
            rest[code] -= 2
            for sets in _decompose(rest):
                if len(sets) == n_melds:
                    melds = [Meld(kind, codes, True) for kind, codes in sets]
                    out.append((melds, code))
    return out


def _is_chiitoitsu(codes: list[str]) -> bool:
    c = Counter(codes)
    return len(c) == 7 and all(v == 2 for v in c.values())


def _is_kokushi(codes: list[str]) -> bool:
    needed = {f"{r}{s}" for s in "BCD" for r in (1, 9)} | set(HONORS)
    c = Counter(codes)
    return set(c) == needed and len(codes) == 14 and any(v == 2 for v in c.values())


# --- wait type ----------------------------------------------------------

def _wait_type(meld: Meld, win_tile: str, is_pair: bool) -> str:
    if is_pair:
        return "tanki"
    if meld.kind == "chow":
        a, b, c = (_rank(x) for x in meld.codes)
        w = _rank(win_tile)
        if w == b:
            return "kanchan"
        # edge wait: 1-2-3 completed by the 3, or 7-8-9 completed by the 7
        if (meld.codes[0][0] == "1" and w == 3) or (meld.codes[2][0] == "9" and w == 7):
            return "penchan"
        return "ryanmen"
    if meld.kind in ("pung", "kan"):
        return "shanpon"
    return "ryanmen"


# --- yaku detection -----------------------------------------------------

def _detect(melds: list[Meld], pair: Meld, ctx: WinContext, closed: bool, wait: str):
    """Return (yaku list[(name,han)], yakuman list[str])."""
    yaku: list[tuple[str, int]] = []
    yakuman: list[str] = []
    all_sets = melds + [pair]
    all_codes = [c for m in all_sets for c in m.codes]
    chows = [m for m in melds if m.kind == "chow"]
    pungs = [m for m in melds if m.kind in ("pung", "kan")]
    suits = {_suit(c) for c in all_codes if _suit(c)}
    has_honor = any(_is_honor(c) for c in all_codes)

    def add(name, han):
        yaku.append((name, han))

    # --- flag-based yaku
    if ctx.riichi and not ctx.double_riichi:
        add("Riichi", 1)
    if ctx.double_riichi:
        add("Double Riichi", 2)
    if ctx.ippatsu:
        add("Ippatsu", 1)
    if closed and ctx.tsumo:
        add("Menzen Tsumo", 1)
    if ctx.haitei:
        add("Haitei", 1)
    if ctx.houtei:
        add("Houtei", 1)
    if ctx.rinshan:
        add("Rinshan", 1)
    if ctx.chankan:
        add("Chankan", 1)

    # --- yakuhai (dragons + winds)
    for m in pungs:
        if m.lead in DRAGONS:
            add(f"Yakuhai ({m.lead})", 1)
        elif m.lead == ctx.seat_wind:
            add("Yakuhai (seat wind)", 1)
        elif m.lead == ctx.round_wind:
            add("Yakuhai (round wind)", 1)
        if m.lead == ctx.seat_wind and m.lead == ctx.round_wind:
            add("Yakuhai (double wind)", 1)  # extra han when seat==round

    # --- tanyao
    if not any(_is_tro(c) for c in all_codes):
        add("Tanyao", 1)

    # --- pinfu (closed, all chows, non-yakuhai pair, ryanmen)
    pair_yakuhai = pair.lead in DRAGONS or pair.lead == ctx.seat_wind or pair.lead == ctx.round_wind
    if closed and len(chows) == 4 and not pair_yakuhai and wait == "ryanmen":
        add("Pinfu", 1)

    # --- iipeikou / ryanpeikou (closed)
    if closed:
        chow_keys = Counter(m.codes for m in chows)
        dups = sum(v // 2 for v in chow_keys.values())
        if dups == 2:
            add("Ryanpeikou", 3)
        elif dups == 1:
            add("Iipeikou", 1)

    # --- sanshoku doujun (same sequence, 3 suits)
    chow_codes = {m.codes for m in chows}
    for start in range(1, 8):
        triple = {(f"{start}{s}", f"{start+1}{s}", f"{start+2}{s}") for s in "BCD"}
        if triple <= chow_codes:
            add("Sanshoku", 2 if closed else 1)
            break

    # --- sanshoku doukou (same triplet, 3 suits)
    pung_ranks = {}
    for m in pungs:
        if _suit(m.lead):
            pung_ranks.setdefault(_rank(m.lead), set()).add(_suit(m.lead))
    if any(len(s) == 3 for s in pung_ranks.values()):
        add("Sanshoku Doukou", 2)

    # --- ittsuu (123-456-789 same suit)
    for s in "BCD":
        need = {(f"1{s}", f"2{s}", f"3{s}"), (f"4{s}", f"5{s}", f"6{s}"), (f"7{s}", f"8{s}", f"9{s}")}
        if need <= {m.codes for m in chows}:
            add("Ittsuu", 2 if closed else 1)
            break

    # --- chanta / junchan (terminal/honor in every set)
    if all(m.is_tro for m in all_sets):
        if all(m.kind in ("pung", "kan") or _is_honor(m.lead) for m in all_sets):
            pass  # handled by honroutou below (no chows)
        if chows:  # needs a sequence to be chanta/junchan rather than honroutou
            if has_honor:
                add("Chanta", 2 if closed else 1)
            else:
                add("Junchan", 3 if closed else 2)

    # --- toitoi / sanankou / sankantsu
    if len(pungs) == 4:
        add("Toitoi", 2)
    concealed_triplets = [m for m in pungs if m.concealed]
    if len(concealed_triplets) == 3:
        add("Sanankou", 2)
    if sum(1 for m in pungs if m.kind == "kan") == 3:
        add("Sankantsu", 2)

    # --- honroutou (all terminals/honors)
    if all(_is_tro(c) for c in all_codes) and not chows:
        add("Honroutou", 2)

    # --- shousangen (2 dragon pungs + dragon pair)
    dragon_pungs = [m for m in pungs if m.lead in DRAGONS]
    if len(dragon_pungs) == 2 and pair.lead in DRAGONS:
        add("Shousangen", 2)

    # --- flushes
    if len(suits) == 1 and not has_honor:
        add("Chinitsu", 6 if closed else 5)
    elif len(suits) == 1 and has_honor:
        add("Honitsu", 3 if closed else 2)

    # ============ YAKUMAN ============
    # daisangen
    if len(dragon_pungs) == 3:
        yakuman.append("Daisangen")
    wind_pungs = [m for m in pungs if m.lead in WINDS]
    if len(wind_pungs) == 4:
        yakuman.append("Daisuushii")  # double in some rules; counted single here
    elif len(wind_pungs) == 3 and pair.lead in WINDS:
        yakuman.append("Shousuushii")
    if all(_is_honor(c) for c in all_codes):
        yakuman.append("Tsuuiisou")
    if all(_is_terminal(c) for c in all_codes):
        yakuman.append("Chinroutou")
    if all(c in GREEN for c in all_codes):
        yakuman.append("Ryuuiisou")
    if sum(1 for m in pungs if m.kind == "kan") == 4:
        yakuman.append("Suukantsu")
    if len(concealed_triplets) == 4:
        yakuman.append("Suuankou")
    if ctx.tenhou:
        yakuman.append("Tenhou")
    if ctx.chiihou:
        yakuman.append("Chiihou")

    return yaku, yakuman


def _han_from_yaku(yaku: list[tuple[str, int]]) -> int:
    return sum(h for _, h in yaku)


def _compute_fu(melds: list[Meld], pair: Meld, ctx: WinContext, closed: bool, wait: str,
                pinfu: bool = False) -> int:
    if pinfu:
        return 20 if ctx.tsumo else 30
    fu = BASE_FU
    if closed and not ctx.tsumo:
        fu += MENZEN_RON_FU
    if ctx.tsumo:
        fu += TSUMO_FU
    if wait in ("kanchan", "penchan", "tanki"):
        fu += 2
    if pair.lead in DRAGONS or pair.lead == ctx.seat_wind or pair.lead == ctx.round_wind:
        fu += YAKUHAI_PAIR_FU
    for m in melds:
        if m.kind == "chow":
            continue
        tro = m.is_tro
        if m.kind == "kan":
            base = 16 if m.concealed else 8
        else:  # pung
            base = 4 if m.concealed else 2
        fu += base * (2 if tro else 1)
    rounded = -(-fu // 10) * 10
    if not closed and rounded == BASE_FU:
        return OPEN_PINFU_FU
    return rounded


# --- main entry ---------------------------------------------------------

def analyze(concealed: list[str], called: list[CalledMeld], ctx: WinContext) -> AnalyzeResult:
    called = called or []
    called_melds = [Meld(m.kind, tuple(m.codes), m.concealed) for m in called]
    # full 14 "counting" tiles = concealed + 3 per called meld (kan's 4th excluded)
    full_codes = list(concealed) + [c for m in called for c in m.codes[:3]]
    closed = all(m.concealed for m in called_melds)  # ankan keeps hand closed

    # ----- thirteen orphans (never overlaps a standard parse) -----
    if not called and _is_kokushi(full_codes):
        return _score_candidate([], ["Kokushi Musou"], 0, ctx)

    candidates: list[AnalyzeResult] = []

    # ----- seven pairs (competes with standard parses; e.g. ryanpeikou wins) -----
    if not called and _is_chiitoitsu(full_codes):
        candidates.append(_chiitoitsu_candidate(full_codes, ctx))

    # The winning tile is part of `concealed` (it always joins the closed hand).
    n_melds = 4 - len(called_melds)
    parses = _standard_parses(list(concealed), n_melds)
    if not parses and not candidates:
        return AnalyzeResult(ok=False, error="not a valid winning hand")

    best: AnalyzeResult | None = None
    for cand in candidates:
        if cand.ok and (best is None or _better(cand, best)):
            best = cand
    for parse_melds, pair_code in (parses or []):
        melds = called_melds + parse_melds
        if pair_code is None:
            continue
        pair = Meld("pair", (pair_code, pair_code), True)
        # enumerate which group the winning tile completes (affects wait + ron-open)
        for assign in _win_assignments(melds, pair, ctx):
            a_melds, a_pair, wait = assign
            yaku, yakuman = _detect(a_melds, a_pair, ctx, closed, wait)
            if not yakuman and _han_from_yaku(yaku) == 0:
                continue  # no yaku => not a legal win (dora alone doesn't count)
            is_pinfu = any(n == "Pinfu" for n, _ in yaku)
            fu = _compute_fu(a_melds, a_pair, ctx, closed, wait, pinfu=is_pinfu)
            cand = _score_candidate(yaku, yakuman, fu, ctx)
            if best is None or _better(cand, best):
                best = cand
    if best is None:
        return AnalyzeResult(ok=False, error="no yaku (hand has no scoring element)")
    return best


def _win_assignments(melds: list[Meld], pair: Meld, ctx: WinContext):
    """Yield (melds, pair, wait) variants for where the winning tile sits.
    For a ron-completed triplet, that triplet becomes open (minko)."""
    w = ctx.win_tile
    seen = False
    # pair wait
    if pair.lead == w:
        yield melds, pair, "tanki"
        seen = True
    for i, m in enumerate(melds):
        if w in m.codes:
            wait = _wait_type(m, w, False)
            adj = list(melds)
            if m.kind == "pung" and not ctx.tsumo:
                adj[i] = Meld(m.kind, m.codes, concealed=False)  # ron shanpon -> open
            yield adj, pair, wait
            seen = True
    if not seen:
        yield melds, pair, "ryanmen"


def _dealer(ctx: WinContext) -> bool:
    return ctx.seat_wind == "EW"


def _score_candidate(yaku, yakuman, fu, ctx: WinContext) -> AnalyzeResult:
    dealer = _dealer(ctx)
    if yakuman:
        from .yaku import YAKUMAN_BY_KEY  # noqa
        # map detected names to multipliers (single unless known double)
        mult = len(yakuman)
        s = scoring.score(0, 0, dealer=dealer, tsumo=ctx.tsumo, players=ctx.players,
                          honba=ctx.honba, riichi_sticks=ctx.riichi_sticks, yakuman=mult)
        return AnalyzeResult(ok=True, yaku=[(y[0], 0) for y in yaku if y[0] != "__"],
                             yakuman=yakuman, han=0, fu=0, score=s)
    han = _han_from_yaku(yaku) + ctx.dora + ctx.aka + ctx.ura
    s = scoring.score(han, fu, dealer=dealer, tsumo=ctx.tsumo, players=ctx.players,
                      honba=ctx.honba, riichi_sticks=ctx.riichi_sticks, kiriage=ctx.kiriage)
    yk = list(yaku)
    if ctx.dora:
        yk.append(("Dora", ctx.dora))
    if ctx.aka:
        yk.append(("Aka dora", ctx.aka))
    if ctx.ura:
        yk.append(("Ura dora", ctx.ura))
    return AnalyzeResult(ok=True, yaku=yk, yakuman=[], han=han, fu=fu, score=s)


def _chiitoitsu_candidate(full_codes: list[str], ctx: WinContext) -> AnalyzeResult:
    """Seven pairs: always closed, fixed 25 fu, 2 han + flags + flush + dora."""
    yaku: list[tuple[str, int]] = [("Chiitoitsu", 2)]
    if ctx.riichi and not ctx.double_riichi:
        yaku.append(("Riichi", 1))
    if ctx.double_riichi:
        yaku.append(("Double Riichi", 2))
    if ctx.ippatsu:
        yaku.append(("Ippatsu", 1))
    if ctx.tsumo:
        yaku.append(("Menzen Tsumo", 1))
    if ctx.haitei:
        yaku.append(("Haitei", 1))
    if ctx.houtei:
        yaku.append(("Houtei", 1))
    suits = {_suit(c) for c in full_codes if _suit(c)}
    has_honor = any(_is_honor(c) for c in full_codes)
    if not any(_is_tro(c) for c in full_codes):
        yaku.append(("Tanyao", 1))
    if len(suits) == 1 and not has_honor:
        yaku.append(("Chinitsu", 6))
    elif len(suits) == 1 and has_honor:
        yaku.append(("Honitsu", 3))
    return _score_candidate(yaku, [], 25, ctx)


def _better(a: AnalyzeResult, b: AnalyzeResult) -> bool:
    """Higher total payout wins (riichi 'highest interpretation' rule)."""
    return a.score.from_payments > b.score.from_payments
