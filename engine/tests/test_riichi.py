from engine.riichi.fu import FuHand, Meld, calc_fu
from engine.riichi.scoring import score
from engine.riichi.yaku import total_han, total_yakuman


# --- scoring: ron (known reference values) ------------------------------

def test_ron_nondealer_basic():
    assert score(1, 30, dealer=False, tsumo=False).total_gain == 1000
    assert score(3, 30, dealer=False, tsumo=False).total_gain == 3900
    assert score(4, 30, dealer=False, tsumo=False).total_gain == 7700


def test_ron_dealer_basic():
    assert score(1, 30, dealer=True, tsumo=False).total_gain == 1500


def test_kiriage_mangan():
    assert score(4, 30, dealer=False, tsumo=False, kiriage=True).limit == "Mangan (kiriage)"
    assert score(4, 30, dealer=False, tsumo=False, kiriage=True).total_gain == 8000


def test_mangan_ron():
    assert score(5, 30, dealer=False, tsumo=False).total_gain == 8000   # non-dealer mangan
    assert score(5, 30, dealer=True, tsumo=False).total_gain == 12000   # dealer mangan
    assert score(5, 30, dealer=False, tsumo=False).limit == "Mangan"


def test_limit_categories():
    assert score(7, 30, dealer=False, tsumo=False).limit == "Haneman"
    assert score(7, 30, dealer=False, tsumo=False).total_gain == 12000  # 3000 base * 4
    assert score(9, 30, dealer=False, tsumo=False).limit == "Baiman"
    assert score(11, 30, dealer=False, tsumo=False).limit == "Sanbaiman"
    assert score(13, 30, dealer=False, tsumo=False).limit == "Kazoe Yakuman"
    assert score(13, 30, dealer=False, tsumo=False).total_gain == 32000  # 8000 * 4


def test_chiitoitsu_ron():
    # 2 han 25 fu non-dealer ron = 1600
    assert score(2, 25, dealer=False, tsumo=False).total_gain == 1600


# --- scoring: tsumo (4-player) -----------------------------------------

def test_tsumo_nondealer_4p():
    s = score(2, 30, dealer=False, tsumo=True, players=4)
    amounts = {p.role: p.amount for p in s.payments}
    assert amounts["dealer"] == 1000 and amounts["non-dealer"] == 500
    assert s.total_gain == 2000  # 1000 + 500 + 500


def test_tsumo_dealer_4p():
    s = score(5, 30, dealer=True, tsumo=True, players=4)
    assert s.payments[0].role == "non-dealer" and s.payments[0].amount == 4000
    assert s.payments[0].count == 3
    assert s.total_gain == 12000


# --- scoring: tsumo (3-player sanma) -----------------------------------

def test_tsumo_nondealer_sanma():
    s = score(5, 30, dealer=False, tsumo=True, players=3)  # mangan
    amounts = {p.role: (p.amount, p.count) for p in s.payments}
    assert amounts["dealer"] == (4000, 1)
    assert amounts["non-dealer"] == (2000, 1)   # only ONE other non-dealer pays
    assert s.total_gain == 6000


def test_tsumo_dealer_sanma():
    s = score(5, 30, dealer=True, tsumo=True, players=3)
    assert s.payments[0].amount == 4000 and s.payments[0].count == 2
    assert s.total_gain == 8000


# --- honba + riichi sticks ---------------------------------------------

def test_honba_ron():
    assert score(1, 30, dealer=False, tsumo=False, honba=2).total_gain == 1600  # 1000 + 600


def test_honba_tsumo():
    s = score(2, 30, dealer=False, tsumo=True, players=4, honba=1)
    # dealer 1000+100, each non-dealer 500+100
    assert s.total_gain == 1100 + 600 + 600


def test_riichi_sticks():
    s = score(5, 30, dealer=False, tsumo=False, riichi_sticks=1)
    assert s.from_payments == 8000
    assert s.total_gain == 9000


# --- explicit yakuman --------------------------------------------------

def test_yakuman():
    assert score(0, 0, dealer=False, tsumo=False, yakuman=1).total_gain == 32000
    assert score(0, 0, dealer=True, tsumo=False, yakuman=1).total_gain == 48000
    assert score(0, 0, dealer=False, tsumo=False, yakuman=2).total_gain == 64000  # double


# --- fu calculation ----------------------------------------------------

def test_fu_specials():
    assert calc_fu(FuHand(closed=True, tsumo=True, pinfu=True)) == 20
    assert calc_fu(FuHand(closed=True, tsumo=False, pinfu=True)) == 30
    assert calc_fu(FuHand(closed=True, tsumo=False, chiitoitsu=True)) == 25


def test_fu_open_pinfu_bump():
    # open, all chows, ryanmen, plain pair, ron -> 20 computed -> bumped to 30
    h = FuHand(closed=False, tsumo=False, wait="ryanmen", melds=[Meld("chow")] * 4)
    assert calc_fu(h) == 30


def test_fu_closed_ron_plain():
    h = FuHand(closed=True, tsumo=False, wait="ryanmen", melds=[Meld("chow")] * 4)
    assert calc_fu(h) == 30  # 20 + 10 menzen


def test_fu_components_roundup():
    # closed ron + closed kan of honors (32) -> 20 + 10 + 32 = 62 -> 70
    h = FuHand(closed=True, tsumo=False, melds=[Meld("closed_kan", True)])
    assert calc_fu(h) == 70


# --- yaku han totals ---------------------------------------------------

def test_total_han_closed():
    assert total_han(["riichi", "tanyao", "pinfu"], closed=True) == 3


def test_total_han_open_kuisagari():
    assert total_han(["chinitsu"], closed=True) == 6
    assert total_han(["chinitsu"], closed=False) == 5  # open reduction
    assert total_han(["tanyao"], closed=False, dora=2) == 3


def test_total_han_closed_only_rejected():
    try:
        total_han(["chiitoitsu"], closed=False)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_total_yakuman():
    assert total_yakuman(["daisangen"]) == 1
    assert total_yakuman(["suuankou_tanki"]) == 2
    assert total_yakuman(["daisangen", "tsuuiisou"]) == 2


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
