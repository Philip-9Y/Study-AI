"""插件加载、启停、安装测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.plugins as plugins_module  # noqa: E402
from core.config import Config  # noqa: E402
from core.plugins import PluginManager  # noqa: E402
from core.tools import ToolRegistry  # noqa: E402

PLUGIN_JSON = """{
  "name": "demo-plugin",
  "version": "1.0.0",
  "description": "测试插件",
  "author": "test"
}"""

PLUGIN_TOOL = """\
from core.tools import ToolSpec

def register(registry):
    registry.register(ToolSpec(
        name="demo_hello",
        description="say hello",
        parameters={"type": "object", "properties": {}},
        func=lambda: "hello from plugin",
    ))
"""


class PluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.builtin = self.root / "builtin"
        self.user = self.root / "user"
        self.builtin.mkdir()
        self.user.mkdir()
        self._old_builtin = plugins_module.BUILTIN_DIR
        self._old_user = plugins_module.USER_DIR
        plugins_module.BUILTIN_DIR = self.builtin
        plugins_module.USER_DIR = self.user

        plugin_dir = self.builtin / "demo_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(PLUGIN_JSON, encoding="utf-8")
        (plugin_dir / "tool.py").write_text(PLUGIN_TOOL, encoding="utf-8")

        self.config = Config(path=self.root / "config.json")
        self.registry = ToolRegistry()
        self.manager = PluginManager(self.config, self.registry)

    def tearDown(self) -> None:
        plugins_module.BUILTIN_DIR = self._old_builtin
        plugins_module.USER_DIR = self._old_user
        self.tmp.cleanup()

    def test_load_and_disable_plugin(self) -> None:
        infos = self.manager.load_all()
        self.assertEqual(len(infos), 1)
        info = infos[0]
        self.assertTrue(info.loaded)
        self.assertEqual(info.tools, ["demo_hello"])
        self.assertIn("demo_hello", self.registry.names())

        self.manager.set_enabled("demo-plugin", False)
        self.assertNotIn("demo_hello", self.registry.names())

        self.manager.set_enabled("demo-plugin", True)
        self.assertIn("demo_hello", self.registry.names())

    def test_install_and_uninstall_from_folder(self) -> None:
        source = self.root / "source_plugin"
        source.mkdir()
        (source / "plugin.json").write_text(
            PLUGIN_JSON.replace("demo-plugin", "another-plugin"), encoding="utf-8"
        )
        (source / "tool.py").write_text(
            PLUGIN_TOOL.replace("demo_hello", "demo_hello2").replace(
                "hello from plugin", "hello from another plugin"
            ),
            encoding="utf-8",
        )

        info = self.manager.install_from_folder(source)
        self.assertTrue(info.loaded)
        self.assertIn("demo_hello2", self.registry.names())
        self.assertTrue((self.user / "another-plugin").exists())

        self.manager.uninstall("another-plugin")
        self.assertFalse((self.user / "another-plugin").exists())
        self.assertNotIn("demo_hello2", self.registry.names())


if __name__ == "__main__":
    unittest.main()
