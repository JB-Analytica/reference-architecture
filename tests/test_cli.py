from typer.testing import CliRunner

from refarch.cli import app


def test_help_lists_every_stage() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in ("generate", "load", "transform", "deploy", "run"):
        assert stage in result.output


def test_gcp_project_has_no_default(monkeypatch) -> None:
    """A fresh clone must not silently aim at whoever built this repo.

    An earlier version shipped a hardcoded default, which meant a clone with no .env pointed at
    somebody else's BigQuery instead of failing.
    """
    import pytest

    from refarch.config import settings

    monkeypatch.delenv("GCP_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="GCP_PROJECT is not set"):
        settings()
