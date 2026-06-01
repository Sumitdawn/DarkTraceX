from pathlib import Path
from darktracex.config import AppConfig


def test_config_bootstrap_creates_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    old_home = Path.home

    class FakeHome:
        def __call__(self):
            return home

    Path.home = FakeHome()
    config = AppConfig.bootstrap()
    assert config.data_dir.exists()
    assert config.plugins_dir.exists()
    assert config.config_path.exists()
    Path.home = old_home
