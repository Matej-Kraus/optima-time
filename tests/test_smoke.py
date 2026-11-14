from optima_time import __version__
from optima_time.cli import main


def test_version_is_set() -> None:
    assert __version__


def test_cli_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert "optima-time" in capsys.readouterr().out


def test_czech_output_survives_a_cp1252_console(capsys) -> None:
    import io
    import sys

    from optima_time.cli import utf8_console

    raw = io.BytesIO()
    old = sys.stdout
    sys.stdout = io.TextIOWrapper(raw, encoding="cp1252")
    try:
        utf8_console()
        print("Přístup ze sítě, ů")
        sys.stdout.flush()
    finally:
        sys.stdout = old
    assert "ů".encode() in raw.getvalue()
