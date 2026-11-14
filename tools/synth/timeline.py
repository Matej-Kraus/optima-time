"""A floorball match timeline, simulated in tenths of a second.

Produces what the board shows at each tenth (board texts, "" = unlit) plus intervals when the
board doesn't show the score (goal animation) and when a person covers part of it.
Deterministic for a given seed.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

FIELDS = ("Time", "period", "scoreh", "scorea", "penaltyh1", "penaltyh2", "penaltya1", "penaltya2")
PENALTY_TENTHS = 2 * 60 * 10


@dataclass(frozen=True)
class BoardState:
    texts: tuple[str, ...]  # in FIELDS order, as shown on the board ("" = unlit)

    def as_dict(self) -> dict[str, str]:
        return dict(zip(FIELDS, self.texts, strict=True))


@dataclass
class Interval:
    start: int  # tenth, inclusive
    end: int  # tenth, exclusive
    kind: str  # "foreign" (whole board shows something else) | "occlusion" (a person walks by)


@dataclass
class Timeline:
    states: list[BoardState]  # one per tenth
    intervals: list[Interval] = field(default_factory=list)

    @property
    def tenths(self) -> int:
        return len(self.states)

    def hidden(self, tenth: int) -> set[str]:
        """Fields hidden by foreign content at this tenth. Which fields a person covers depends
        on the camera geometry, so the renderer works that out (synth.__main__)."""
        return set(FIELDS) if self.foreign(tenth) else set()

    def foreign(self, tenth: int) -> bool:
        return any(iv.kind == "foreign" and iv.start <= tenth < iv.end for iv in self.intervals)


def clock_text(remaining: int, tenths_in_last_minute: bool) -> str:
    """Board text of a count-down clock with `remaining` tenths: "05:13", "59.9", "0.0"."""
    if tenths_in_last_minute and remaining < 600:
        return f"{remaining // 10}.{remaining % 10}"
    secs = math.ceil(remaining / 10)
    return f"{secs // 60:02d}:{secs % 60:02d}"


def count_up_text(elapsed: int) -> str:
    secs = elapsed // 10
    return f"{secs // 60:02d}:{secs % 60:02d}"


def penalty_text(remaining: int) -> str:
    secs = math.ceil(remaining / 10)
    return f"{secs // 60}:{secs % 60:02d}"


@dataclass
class _Game:
    tenths_in_last_minute: bool
    direction: str  # "down" | "up"
    period_tenths: int = 20 * 60 * 10
    period: int = 1
    remaining: int = 0  # game clock, tenths left in the period
    running: bool = False
    intermission: int | None = None  # tenths left of the intermission countdown
    score: list[int] = field(default_factory=lambda: [0, 0])
    penalties: list[list[int]] = field(default_factory=lambda: [[], []])  # tenths left

    def tick(self) -> None:
        if self.intermission is not None:
            self.intermission = max(0, self.intermission - 1)
            return
        if not self.running:
            return
        self.remaining = max(0, self.remaining - 1)
        for team in self.penalties:
            team[:] = [p - 1 for p in team if p - 1 > 0]
        if self.remaining == 0:
            self.running = False

    def state(self) -> BoardState:
        if self.intermission is not None:
            time = clock_text(self.intermission, False)
        elif self.direction == "up":
            time = count_up_text(self.period_tenths - self.remaining)
        else:
            time = clock_text(self.remaining, self.tenths_in_last_minute)
        pens = [[penalty_text(p) for p in team[:2]] + ["", ""] for team in self.penalties]
        return BoardState(
            (
                time,
                str(self.period),
                str(self.score[0]),
                str(self.score[1]),
                pens[0][0],
                pens[0][1],
                pens[1][0],
                pens[1][1],
            )
        )


def simulate(
    seed: int = 1,
    tenths_in_last_minute: bool = True,
    direction: str = "down",
    short: bool = False,
) -> Timeline:
    """The default scenario (~4 min) covers: an intermission countdown over 20:00, a period
    running into its last minute with tenths, goals 9 -> 10, penalties (two at once per team,
    expiring), stoppages, the period end, a new period starting at 20:00, a goal animation and
    a person walking in front of the board. `short` gives ~25 s for tests."""
    rng = random.Random(seed)
    g = _Game(tenths_in_last_minute, direction)
    states: list[BoardState] = []
    intervals: list[Interval] = []
    t = 0

    def run(n: int) -> None:
        nonlocal t
        for _ in range(n):
            states.append(g.state())
            g.tick()
            t += 1

    def goal(team: int, animation: bool = True) -> None:
        g.score[team] += 1
        g.running = False
        if animation:
            length = rng.randint(30, 50)
            intervals.append(Interval(t + 5, t + 5 + length, "foreign"))

    def penalty(team: int) -> None:
        if len(g.penalties[team]) < 2:
            g.penalties[team].append(PENALTY_TENTHS)

    if short:
        g.score = [9, 3]
        g.remaining = 75 * 10  # 1:15 left: runs into the tenths
        g.running = True
        penalty(0)
        run(80)
        goal(0)  # 9 -> 10
        run(60)
        g.running = True
        run(60)
        intervals.append(Interval(t, t + 15, "occlusion"))
        run(50)
        return Timeline(states, intervals)

    # 1) intermission before the period, counting down from 23:54 (over 20:00)
    g.score = [rng.randint(7, 9), rng.randint(0, 3)]
    g.intermission = (23 * 60 + 54) * 10
    run(120)
    # 2) period 1 already running, 2:30 left
    g.intermission = None
    g.remaining = 150 * 10
    g.running = True
    run(rng.randint(80, 120))
    penalty(0)
    run(rng.randint(60, 90))
    penalty(1)
    run(40)
    penalty(1)  # two at once for the away team
    run(rng.randint(80, 120))
    g.running = False  # stoppage
    run(rng.randint(40, 60))
    penalty(0)  # second home penalty while the first runs
    g.running = True
    run(150)
    while g.score[0] < 10:  # score goes over 9 -> 10
        goal(0)
        run(rng.randint(40, 60))
    g.running = True
    intervals.append(Interval(t + 20, t + 35, "occlusion"))
    while g.remaining > 0:  # into the last minute with tenths, down to 0.0
        run(1)
    run(50)
    # 3) period 2 starts at 20:00
    g.period = 2
    g.remaining = g.period_tenths
    run(rng.randint(30, 50))
    g.running = True
    run(rng.randint(150, 250))
    goal(1)
    run(rng.randint(60, 80))
    g.running = True
    penalty(0)
    run(rng.randint(150, 200))
    return Timeline(states, intervals)
