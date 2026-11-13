from optima_time import __version__
from optima_time.cli import main


def test_version_is_set() -> None:
    assert __version__


def test_cli_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert "optima-time" in capsys.readouterr().out
