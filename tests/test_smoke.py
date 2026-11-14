from optima_time import __version__
from optima_time.cli import main


def test_version_is_set() -> None:
    assert __version__


def test_cli_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert "optima-time" in capsys.readouterr().out


def test_czech_output_survives_a_cp1252_console(monkeypatch) -> None:
    import io
    import sys

    from optima_time.cli import utf8_console

    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    utf8_console()
    console.write("Přístup ze sítě, ů\n")
    console.flush()
    data = raw.getvalue()
    console.detach()  # keep raw open for the assertion
    assert "ů".encode() in data
