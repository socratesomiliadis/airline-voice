"""CLI discovery does not start autonomous work."""

import pytest
from airline_refiner.cli import main


def test_worker_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["airline-refiner", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert "Autonomously simulate" in capsys.readouterr().out
