from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
import tomllib

DEFAULT_CONFIG = {
    "database": {
        "url": "sqlite:///{}"
    },
    "workspace": {
        "path": "{}"
    },
    "plugins": {
        "path": "{}"
    }
}


@dataclass
class AppConfig:
    workspace_dir: Path
    data_dir: Path
    db_url: str
    plugins_dir: Path
    loaded_plugins: list[str] = field(default_factory=list)
    config_path: Path | None = None

    @classmethod
    def bootstrap(cls) -> "AppConfig":
        home = Path.home()
        root = home / ".darktracex"
        root.mkdir(parents=True, exist_ok=True)

        config_path = root / "config.toml"
        default_db = f"sqlite:///{(root / 'darktracex.db').as_posix()}"
        default_workspace = root.as_posix()
        default_plugin_path = (Path.cwd() / "plugins").as_posix()

        if not config_path.exists():
            config_text = (
                f"[database]\nurl = \"{default_db}\"\n"
                f"[workspace]\npath = \"{default_workspace}\"\n"
                f"[plugins]\npath = \"{default_plugin_path}\"\n"
            )
            config_path.write_text(config_text, encoding="utf-8")

        text = config_path.read_text(encoding="utf-8")
        try:
            config_data = tomllib.loads(text)
        except Exception:
            config_path.write_text(
                f"[database]\nurl = \"{default_db}\"\n"
                f"[workspace]\npath = \"{default_workspace}\"\n"
                f"[plugins]\npath = \"{default_plugin_path}\"\n",
                encoding="utf-8"
            )
            config_data = tomllib.loads(config_path.read_text(encoding="utf-8"))

        db_url = config_data.get("database", {}).get("url")
        if not db_url or not db_url.startswith("sqlite:///"):
            db_url = default_db
        elif os.name == "nt" and db_url.startswith("sqlite:///"):
            windows_path = db_url[len("sqlite:///"):]
            if windows_path.startswith("/") and ":" not in windows_path[:3]:
                db_url = default_db

        workspace_dir = Path(config_data.get("workspace", {}).get("path", default_workspace))
        plugins_dir = Path(config_data.get("plugins", {}).get("path", default_plugin_path))

        workspace_dir.mkdir(parents=True, exist_ok=True)
        plugins_dir.mkdir(parents=True, exist_ok=True)

        config = cls(
            workspace_dir=workspace_dir,
            data_dir=root,
            db_url=db_url,
            plugins_dir=plugins_dir,
            config_path=config_path,
        )

        if db_url != config_data.get("database", {}).get("url"):
            config.save()

        return config

    def save(self) -> None:
        content = (
            f"[database]\nurl = \"{self.db_url}\"\n"
            f"[workspace]\npath = \"{self.workspace_dir.as_posix()}\"\n"
            f"[plugins]\npath = \"{self.plugins_dir.as_posix()}\"\n"
        )
        if self.config_path is not None:
            self.config_path.write_text(content, encoding="utf-8")
