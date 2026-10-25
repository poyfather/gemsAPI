"""The API reports the version from app.version."""
from app.main import app
from app.version import __version__


def test_app_version_comes_from_version_py() -> None:
    assert app.version == __version__
    assert __version__.count(".") == 2
