"""Krita context validation and docker registration."""

import importlib.util
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from krita_test_support import PACKAGE, ROOT, app, context, docker


class PluginTests(unittest.TestCase):
    def load(self, name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_context_uses_krita_instance(self):
        krita = ModuleType("krita")
        krita.Krita = SimpleNamespace(instance=lambda: app)
        with patch.dict(sys.modules, {"krita": krita}):
            context = self.load("_context_test", ROOT / "plugin/stroke_sampler/context.py")
        self.assertIs(context.app, app)

    def test_context_fails_clearly_outside_krita(self):
        krita = ModuleType("krita")
        krita.Krita = SimpleNamespace(instance=lambda: None)
        with patch.dict(sys.modules, {"krita": krita}):
            with self.assertRaisesRegex(RuntimeError, "Krita instance not found"):
                self.load("_context_test", ROOT / "plugin/stroke_sampler/context.py")

    def test_registers_factory_for_docker(self):
        factory = Mock(return_value=object())
        krita = ModuleType("krita")
        krita.DockWidgetFactory = factory
        krita.DockWidgetFactoryBase = SimpleNamespace(DockPosition=SimpleNamespace(DockRight="right"))
        register = Mock()
        modules = {"krita": krita, f"{PACKAGE}.docker": docker, f"{PACKAGE}.context": context}
        with patch.dict(sys.modules, modules), patch.object(app, "addDockWidgetFactory", register, create=True):
            self.load(f"{PACKAGE}.stroke_sampler", ROOT / "plugin/stroke_sampler/stroke_sampler.py")
        factory.assert_called_once_with("stroke_sampler", "right", docker.StrokeSamplerDocker)
        register.assert_called_once_with(factory.return_value)
