from engine.sg.payout import fan_to_value, settle_discard_win, settle_self_draw, settle_kong_fee
from engine.sg.scoring import HandContext, score_hand
from engine.tiles import parse_tiles


def test_chicken_hand():
    tiles = parse_tiles(
        ["1B", "2B", "3B", "4C", "5C", "6C", "7D", "8D", "9D", "2B", "3B", "4B", "5D", "5D"]
    )
    ctx = HandContext(seat_wind="EW", round_wind="EW")
    result = score_hand(tiles, ctx)
    assert result.is_chicken_hand
    assert result.fan == 0


def test_full_flush():
    tiles = parse_tiles(
        ["1B", "2B", "3B", "4B", "5B", "6B", "7B", "8B", "9B", "2B", "3B", "4B", "5B", "5B"]
    )
    ctx = HandContext(seat_wind="EW", round_wind="EW")
    result = score_hand(tiles, ctx)
    assert "Full Flush" in result.breakdown
    assert result.fan == 6


def test_seven_pairs():
    tiles = parse_tiles(
        ["1B", "1B", "2B", "2B", "3B", "3B", "4C", "4C", "5C", "5C", "6D", "6D", "RD", "RD"]
    )
    ctx = HandContext(seat_wind="EW", round_wind="EW")
    result = score_hand(tiles, ctx)
    assert result.fan == 6
    assert "All Pairs (Seven Pairs)" in result.breakdown


def test_fan_to_value_doubling():
    assert fan_to_value(0, base_unit=1) == 1
    assert fan_to_value(1, base_unit=1) == 1
    assert fan_to_value(2, base_unit=1) == 2
    assert fan_to_value(3, base_unit=1) == 4
    assert fan_to_value(10, base_unit=1) == 512
    assert fan_to_value(20, base_unit=1) == 512  # capped at LIMIT_FAN


def test_settle_discard_win():
    transfers = settle_discard_win("Alice", "Bob", value=4)
    assert len(transfers) == 1
    assert transfers[0].payer == "Bob"
    assert transfers[0].payee == "Alice"
    assert transfers[0].amount == 4


def test_settle_self_draw():
    players = ["Alice", "Bob", "Carol", "Dave"]
    transfers = settle_self_draw("Alice", value=2, players=players)
    assert len(transfers) == 3
    assert all(t.amount == 4 for t in transfers)  # 2x discard rate


def test_settle_kong_fee():
    players = ["Alice", "Bob", "Carol", "Dave"]
    transfers = settle_kong_fee("Alice", fee=0.1, players=players)
    assert len(transfers) == 3
    assert all(t.amount == 0.1 and t.payee == "Alice" for t in transfers)


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
