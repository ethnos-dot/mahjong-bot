from engine.riichi.analyze import CalledMeld, WinContext, analyze


def ctx(win, tsumo=False, seat="SW", rnd="EW", **kw):
    return WinContext(seat_wind=seat, round_wind=rnd, win_tile=win, tsumo=tsumo, **kw)


def names(res):
    return {n for n, _ in res.yaku} | set(res.yakuman)


def test_pinfu_tanyao_ron():
    hand = ["2C", "3C", "4C", "6C", "7C", "8C", "3D", "4D", "5D", "6B", "7B", "8B", "5B", "5B"]
    res = analyze(hand, [], ctx("4C"))
    assert res.ok
    assert names(res) == {"Pinfu", "Tanyao"}
    assert res.han == 2 and res.fu == 30
    assert res.score.total_gain == 2000  # non-dealer ron


def test_riichi_tsumo_pinfu_tanyao():
    hand = ["2C", "3C", "4C", "6C", "7C", "8C", "3D", "4D", "5D", "6B", "7B", "8B", "5B", "5B"]
    res = analyze(hand, [], ctx("4C", tsumo=True, riichi=True))
    assert names(res) == {"Riichi", "Menzen Tsumo", "Pinfu", "Tanyao"}
    assert res.han == 4 and res.fu == 20  # pinfu tsumo
    assert res.score.total_gain == 5200  # 1300/2600


def test_yakuhai_open_ron():
    hand = ["1C", "2C", "3C", "4C", "5C", "6C", "7D", "8D", "9D", "2B", "2B"]
    called = [CalledMeld("pung", ("WD", "WD", "WD"), concealed=False)]
    res = analyze(hand, called, ctx("6C"))
    assert "Yakuhai (WD)" in names(res)
    assert res.han == 1 and res.fu == 30
    assert res.score.total_gain == 1000


def test_sanankou_tsumo():
    hand = ["2C", "2C", "2C", "5D", "5D", "5D", "8B", "8B", "8B", "4C", "5C", "6C", "9D", "9D"]
    res = analyze(hand, [], ctx("6C", tsumo=True))
    assert "Sanankou" in names(res) and "Menzen Tsumo" in names(res)
    assert res.han == 3 and res.fu == 40
    assert res.score.total_gain == 5200  # 1300/2600


def test_daisangen_yakuman_ron():
    hand = ["RD", "RD", "RD", "GD", "GD", "GD", "WD", "WD", "WD", "2C", "3C", "4C", "5D", "5D"]
    res = analyze(hand, [], ctx("4C"))
    assert "Daisangen" in res.yakuman
    assert res.score.total_gain == 32000  # non-dealer yakuman ron


def test_kokushi_yakuman_ron():
    hand = ["1C", "9C", "1D", "9D", "1B", "9B", "EW", "SW", "WW", "NW", "RD", "GD", "WD", "RD"]
    res = analyze(hand, [], ctx("RD"))
    assert "Kokushi Musou" in res.yakuman
    assert res.score.total_gain == 32000


def test_chiitoitsu_riichi_ron():
    hand = ["1C", "1C", "4C", "4C", "5D", "5D", "9D", "9D", "3B", "3B", "7B", "7B", "RD", "RD"]
    res = analyze(hand, [], ctx("7B", riichi=True))
    assert "Chiitoitsu" in names(res) and "Riichi" in names(res)
    assert res.han == 3 and res.fu == 25
    assert res.score.total_gain == 3200


def test_dealer_mangan_tsumo():
    # 5+ han closed dealer tsumo -> mangan, 4000 all
    hand = ["2C", "3C", "4C", "6C", "7C", "8C", "3D", "4D", "5D", "6B", "7B", "8B", "5B", "5B"]
    # riichi + tsumo + pinfu + tanyao = 4, + 1 dora = 5 -> mangan
    res = analyze(hand, [], ctx("4C", tsumo=True, seat="EW", riichi=True, dora=1))
    assert res.han == 5
    assert res.score.limit == "Mangan"
    assert res.score.total_gain == 12000  # dealer mangan tsumo


def test_no_yaku_is_invalid():
    # open hand, only dora, no actual yaku -> not a legal win
    hand = ["2C", "3C", "4C", "6C", "7C", "8C", "2B", "2B"]
    called = [CalledMeld("chow", ("3D", "4D", "5D"), concealed=False)]
    res = analyze(hand, called, ctx("4C", dora=3))
    assert not res.ok


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
