"""The worker must expose help without starting any refinement work."""

import pytest
from airline_refiner.cli import main


def test_worker_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["airline-refiner", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert "Execution is not implemented" in capsys.readouterr().out


def test_worker_cannot_execute(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["airline-refiner", "run"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "no work was performed" in capsys.readouterr().err
