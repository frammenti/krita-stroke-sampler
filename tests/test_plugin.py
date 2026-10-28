"""Krita state validation and docker registration."""

import importlib.util
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from krita_test_support import PACKAGE, ROOT, app, state, docker, settings


class PluginTests(unittest.TestCase):
    def load(self, name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_state_uses_krita_instance(self):
        krita = ModuleType("krita")
        krita.Krita = SimpleNamespace(instance=lambda: app)
        with patch.dict(sys.modules, {"krita": krita, f"{PACKAGE}.settings": settings}):
            state = self.load(f"{PACKAGE}._state_test", ROOT / "plugin/stroke_sampler/state.py")
        self.assertIs(state.app, app)

    def test_state_fails_clearly_outside_krita(self):
        krita = ModuleType("krita")
        krita.Krita = SimpleNamespace(instance=lambda: None)
        with patch.dict(sys.modules, {"krita": krita, f"{PACKAGE}.settings": settings}):
            with self.assertRaisesRegex(RuntimeError, "Krita instance not found"):
                self.load(f"{PACKAGE}._state_test", ROOT / "plugin/stroke_sampler/state.py")

    def test_registers_factory_for_docker(self):
        factory = Mock(return_value=object())
        krita = ModuleType("krita")
        krita.DockWidgetFactory = factory
        krita.DockWidgetFactoryBase = SimpleNamespace(DockPosition=SimpleNamespace(DockRight="right"))
        register = Mock()
        extension = ModuleType(f"{PACKAGE}.extension")
        extension.StrokeSamplerExtension = Mock()
        modules = {f"{PACKAGE}.extension": extension, "krita": krita, f"{PACKAGE}.docker": docker, f"{PACKAGE}.state": state}
        with (patch.dict(sys.modules, modules),
              patch.object(app, "addDockWidgetFactory", register, create=True),
              patch.object(app, "addExtension", create=True) as add_extension):
            self.load(f"{PACKAGE}.stroke_sampler", ROOT / "plugin/stroke_sampler/stroke_sampler.py")
        factory.assert_called_once_with("stroke_sampler", "right", docker.StrokeSamplerDocker)
        register.assert_called_once_with(factory.return_value)
        extension.StrokeSamplerExtension.assert_called_once_with(app)
        add_extension.assert_called_once_with(extension.StrokeSamplerExtension.return_value)
