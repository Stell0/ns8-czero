"""The fixture consumes an installed independent Core, not a checkout override."""
from importlib.metadata import version
from pathlib import Path
import unittest
import czero_core
from czero_core.health import core_version


class CoreConsumer(unittest.TestCase):
    def test_installed_core_identity(self):
        installed = version("czero-core")
        self.assertEqual(core_version, installed)
        self.assertEqual(tuple(map(int, installed.split(".")[:2])), (0, 24))
        self.assertFalse((Path.cwd() / "packages/czero-core").exists())
        self.assertNotIn("packages/czero-core/src", str(Path(czero_core.__file__).resolve()))

    def test_independent_import(self):
        from czero_core.objects import ObjectService
        from czero_core.wiki import WikiService
        from czero_core.worker import Worker
        self.assertTrue(all(callable(item) for item in (ObjectService, WikiService, Worker)))
