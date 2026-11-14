from optima_time.alerts import AlertMonitor


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def monitor():
    sent: list[tuple[str, bool]] = []
    clock = Clock()
    m = AlertMonitor(lambda title, _msg, problem: sent.append((title, problem)), clock)
    return m, clock, sent


def test_a_short_dropout_is_not_announced() -> None:
    m, clock, sent = monitor()
    m.check({"source": True})
    clock.t = 2.0
    m.check({"source": True})
    clock.t = 2.5
    m.check({"source": False})
    assert sent == []


def test_a_lasting_problem_is_announced_once_and_its_end_too() -> None:
    m, clock, sent = monitor()
    for t in (0, 1, 3.1, 4, 10):
        clock.t = t
        m.check({"source": True})
    assert sent == [("Zdroj obrazu vypadl", True)]
    clock.t = 11
    m.check({"source": False})
    assert sent[-1] == ("Zdroj obrazu je zpět.", False)
    # a new incident is announced again
    for t in (20, 23.5):
        clock.t = t
        m.check({"source": True})
    assert [p for _, p in sent] == [True, False, True]


def test_guard_waits_a_minute_and_stuck_is_immediate() -> None:
    m, clock, sent = monitor()
    m.check({"guard": True, "stuck": True})
    assert sent == [("Zpracování se zaseklo", True)]
    clock.t = 59
    m.check({"guard": True, "stuck": True})
    assert len(sent) == 1
    clock.t = 60
    m.check({"guard": True, "stuck": True})
    assert sent[-1] == ("Tabule dlouho ukazuje něco jiného", True)
