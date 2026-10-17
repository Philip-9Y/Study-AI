"""插件系统：从 plugins/ 与 data/plugins/ 加载 Python 工具插件。"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from core.config import APP_DIR, DATA_DIR, Config
from core.tools import ToolRegistry

BUILTIN_DIR = APP_DIR / "plugins"
USER_DIR = DATA_DIR / "plugins"


@dataclass
class PluginInfo:
    name: str
    version: str = ""
    description: str = ""
    author: str = ""
    path: Path | None = None
    builtin: bool = False
    enabled: bool = True
    loaded: bool = False
    error: str = ""
    tools: list[str] = field(default_factory=list)


class _RegistryProxy:
    """把插件注册的工具统一标记来源，便于卸载时清理。"""

    def __init__(self, registry: ToolRegistry, source: str) -> None:
        self._registry = registry
        self._source = source

    def register(self, spec) -> None:
        self._registry.register(spec, source=self._source)


class PluginManager:
    def __init__(self, config: Config, registry: ToolRegistry) -> None:
        self.config = config
        self.registry = registry
        self.plugins: dict[str, PluginInfo] = {}
        BUILTIN_DIR.mkdir(parents=True, exist_ok=True)
        USER_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def load_all(self) -> list[PluginInfo]:
        for info in list(self.plugins.values()):
            self.registry.unregister_source(info.name)
        self.plugins.clear()
        for root, builtin in ((BUILTIN_DIR, True), (USER_DIR, False)):
            if not root.exists():
                continue
            for folder in sorted(root.iterdir()):
                if folder.is_dir() and (folder / "plugin.json").exists():
                    info = self._load(folder, builtin)
                    if info.name in self.plugins:
                        info.loaded = False
                        info.error = "插件名重复"
                    self.plugins[info.name] = info
        return self.list_plugins()

    def list_plugins(self) -> list[PluginInfo]:
        return sorted(self.plugins.values(), key=lambda item: (not item.builtin, item.name))

    def set_enabled(self, name: str, enabled: bool) -> None:
        info = self.plugins.get(name)
        if info is None:
            return
        config_plugins = self.config.data.setdefault("plugins", {})
        config_plugins[name] = bool(enabled)
        self.config.save()
        self.load_all()

    def install_from_folder(self, folder: Path) -> PluginInfo:
        folder = Path(folder).resolve()
        if not (folder / "plugin.json").exists():
            raise ValueError("所选文件夹缺少 plugin.json")
        metadata = self._read_metadata(folder)
        name = metadata["name"]
        target = USER_DIR / name
        if target.exists():
            raise ValueError(f"插件 {name} 已存在，请先卸载")
        shutil.copytree(folder, target)
        info = self._load(target, builtin=False)
        self.plugins[info.name] = info
        if not info.loaded:
            shutil.rmtree(target, ignore_errors=True)
            raise ValueError(f"插件加载失败：{info.error}")
        return info

    def install_from_zip(self, zip_path: Path) -> PluginInfo:
        zip_path = Path(zip_path)
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path) as archive:
                for member in archive.namelist():
                    if member.startswith(("/", "\\")) or ".." in member:
                        raise ValueError("压缩包包含非法路径")
                archive.extractall(temp_dir)
            root = Path(temp_dir)
            plugin_root = root if (root / "plugin.json").exists() else None
            if plugin_root is None:
                for child in root.iterdir():
                    if child.is_dir() and (child / "plugin.json").exists():
                        plugin_root = child
                        break
            if plugin_root is None:
                raise ValueError("压缩包里没有找到 plugin.json")
            return self.install_from_folder(plugin_root)

    def uninstall(self, name: str) -> None:
        info = self.plugins.get(name)
        if info is None or info.builtin or info.path is None:
            raise ValueError("内置插件不能卸载")
        self.registry.unregister_source(name)
        self.plugins.pop(name, None)
        if info.path.exists():
            shutil.rmtree(info.path, ignore_errors=True)
        config_plugins = self.config.data.get("plugins", {})
        config_plugins.pop(name, None)
        self.config.save()

    # ------------------------------------------------------------------
    def _read_metadata(self, folder: Path) -> dict:
        try:
            metadata = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"plugin.json 读取失败：{exc}") from exc
        name = str(metadata.get("name") or "").strip()
        if not name or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for char in name):
            raise ValueError("plugin.json 里的 name 只能包含字母数字、-、_、.")
        return metadata

    def _load(self, folder: Path, builtin: bool) -> PluginInfo:
        try:
            metadata = self._read_metadata(folder)
        except ValueError as exc:
            return PluginInfo(name=folder.name, path=folder, builtin=builtin, error=str(exc))
        name = metadata["name"]
        enabled = bool(self.config.data.get("plugins", {}).get(name, True))
        info = PluginInfo(
            name=name,
            version=str(metadata.get("version") or ""),
            description=str(metadata.get("description") or ""),
            author=str(metadata.get("author") or ""),
            path=folder,
            builtin=builtin,
            enabled=enabled,
        )
        if not enabled:
            return info
        entry = folder / str(metadata.get("entry") or "tool.py")
        if not entry.exists():
            info.error = f"入口文件不存在：{entry.name}"
            return info
        try:
            module_name = f"biliask_plugin_{name}_{uuid.uuid4().hex[:6]}"
            spec = importlib.util.spec_from_file_location(module_name, entry)
            if spec is None or spec.loader is None:
                raise ImportError("无法加载入口文件")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise AttributeError("tool.py 缺少 register(registry) 函数")
            before = set(self.registry.names())
            register(_RegistryProxy(self.registry, name))
            after = set(self.registry.names())
            info.tools = sorted(after - before)
            info.loaded = True
        except Exception as exc:  # noqa: BLE001
            self.registry.unregister_source(name)
            info.error = f"{type(exc).__name__}: {exc}"
        return info

    def open_user_dir(self) -> None:
        import os

        os.startfile(str(USER_DIR))  # type: ignore[attr-defined]
