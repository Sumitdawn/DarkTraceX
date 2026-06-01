from __future__ import annotations

import importlib.util
import pkgutil
from pathlib import Path
from types import ModuleType
from .config import AppConfig


class PluginMetadata:
    def __init__(self, name: str, version: str, description: str, module: ModuleType) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.module = module


class PluginRegistry:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.active: list[PluginMetadata] = []

    def discover(self) -> list[PluginMetadata]:
        plugin_folder = self.config.plugins_dir
        if not plugin_folder.exists():
            return []

        results: list[PluginMetadata] = []
        for finder, name, ispkg in pkgutil.iter_modules([str(plugin_folder)]):
            module_name = f"plugins.{name}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_folder / f"{name}.py")
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                metadata = getattr(module, "metadata", None)
                if metadata is not None:
                    results.append(PluginMetadata(metadata.get("name", name), metadata.get("version", "0.0.0"), metadata.get("description", ""), module))
        self.active = results
        return results

    def load(self) -> list[PluginMetadata]:
        return self.discover()
