"""In-memory per-chat game session state (players + running balances).

Lost on bot restart - fine for a first version; swap for persistent storage
later if sessions need to survive restarts.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GameSession:
    players: list[str]
    balances: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for p in self.players:
            self.balances.setdefault(p, 0.0)

    def apply_transfers(self, transfers) -> None:
        for t in transfers:
            self.balances[t.payer] -= t.amount
            self.balances[t.payee] += t.amount


_sessions: dict[int, GameSession] = {}


def start_session(chat_id: int, players: list[str]) -> GameSession:
    session = GameSession(players=players)
    _sessions[chat_id] = session
    return session


def get_session(chat_id: int) -> GameSession | None:
    return _sessions.get(chat_id)


def end_session(chat_id: int) -> None:
    _sessions.pop(chat_id, None)
