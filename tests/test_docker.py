"""Real Qt controls with a Krita API double.

Run: QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
The double models None as an empty Qt string; verify that conversion in Krita.
"""

import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QUuid
from PyQt6.QtWidgets import QApplication, QDockWidget


class Node:
    def __init__(self, name, children=(), kind="paintlayer"):
        self.label = name
        self.children = list(children)
        self.id = QUuid.createUuid()
        self.kind = kind

    def childNodes(self):
        return self.children

    def name(self):
        return self.label

    def uniqueId(self):
        return self.id

    def type(self):
        return self.kind


class Document:
    def __init__(self, children=()):
        self.root = Node("root", children)

    def rootNode(self):
        return self.root

    def nodeByName(self, name):
        def find(parent):
            for node in parent.childNodes():
                if node.name() == name:
                    return node
                result = find(node)
                if result is not None:
                    return result
            return None
        return find(self.root)


class Application:
    def __init__(self):
        self.document = None
        self.values = {}
        self.writes = []
        self.reads = []

    def activeDocument(self):
        return self.document

    def readSetting(self, group, name, default):
        self.reads.append(name)
        return self.values.get(name, default) or ""

    def writeSetting(self, group, name, value):
        self.writes.append((name, value))
        self.values[name] = value or ""


app = Application()
package = types.ModuleType("_sampler_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "plugin" / "stroke_sampler")]
sys.modules[package.__name__] = package
context = types.ModuleType("_sampler_test.context")
context.app = app
krita = types.ModuleType("krita")
krita.Document, krita.Node = Document, Node
krita.Canvas, krita.DockWidget = object, QDockWidget
# Avoid executing plugin registration or requiring a running Krita process.
with patch.dict(sys.modules, {"krita": krita, context.__name__: context}):
    settings = importlib.import_module("_sampler_test.settings")
    docker = importlib.import_module("_sampler_test.docker")


class DockerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        app.document = None
        app.values.clear()
        app.writes.clear()
        app.reads.clear()
        docker._settings = settings.load_settings()
        docker._settings_document = None
        self.docks = []
        self.dock = self.new_dock()

    def new_dock(self):
        dock = docker.StrokeSamplerDocker()
        self.docks.append(dock)
        return dock

    def tearDown(self):
        for dock in self.docks:
            dock._timer.stop()
            dock.deleteLater()
        self.qt.processEvents()

    def activate(self, document):
        app.document = document
        self.dock.canvasChanged(None)

    def select(self, node):
        self.dock.source_layer.setCurrentIndex(
            self.dock.source_layer.findData(node.uniqueId().toString())
        )

    def test_global_controls_without_document_and_refresh_does_not_write(self):
        self.assertFalse(self.dock.source_layer.isEnabled())
        self.assertTrue(self.dock.radius.isEnabled())
        self.assertTrue(self.dock.active.isEnabled())
        self.assertEqual(self.dock.radius.value(), 1)
        self.assertFalse(self.dock.active.isChecked())
        self.activate(Document())
        self.assertFalse(app.writes)
        self.assertTrue(self.dock.source_layer.isEnabled())

    def test_save_user_changes_and_disable_retains_source(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.select(source)
        self.dock.active.setChecked(True)
        self.dock.radius.setValue(7.25)
        self.assertEqual(app.values, {"active": "True", "radius": "7.25", "source_layer_name": "Source"})
        self.dock.active.setChecked(False)
        self.assertIs(docker._settings.source_layer, source)
        self.assertEqual(app.values["source_layer_name"], "Source")
        self.assertEqual(app.values["active"], "False")

    def test_switch_document_matches_name_keeps_other_values(self):
        first, second = Node("Source"), Node("Source")
        self.activate(Document([first]))
        self.select(first)
        self.dock.active.setChecked(True)
        self.dock.radius.setValue(7.25)
        state = docker._settings
        self.activate(Document([second]))
        self.assertIs(docker._settings, state)
        self.assertIs(state.source_layer, second)
        self.assertEqual(self.dock.radius.value(), 7.25)
        self.assertTrue(self.dock.active.isChecked())
        self.assertEqual(self.dock.source_layer.currentData(), second.id.toString())

    def test_missing_match_overwrites_name_on_next_user_save(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.select(source)
        self.activate(Document())
        self.assertIsNone(docker._settings.source_layer)
        self.assertEqual(self.dock.source_layer.currentIndex(), 0)
        self.dock.radius.setValue(2)
        self.assertEqual(app.values["source_layer_name"], "")

    def test_nested_duplicates_rename_reorder_and_delete(self):
        source = Node("Same")
        group = Node("Group", [source], "grouplayer")
        other = Node("Same")
        doc = Document([other, group, Node("Mask", kind="transparencymask")])
        self.activate(doc)
        self.assertEqual(self.dock.source_layer.count(), 4)
        self.select(source)
        self.dock._refresh()
        self.assertIs(docker._settings.source_layer, source)
        source.label = "Renamed"
        doc.root.children.reverse()
        self.dock._refresh()
        self.assertIs(docker._settings.source_layer, source)
        self.assertIn("Renamed", self.dock.source_layer.currentText())
        self.assertEqual(app.values["source_layer_name"], "Renamed")
        group.children.clear()
        self.dock._refresh()
        self.assertIsNone(docker._settings.source_layer)
        self.assertEqual(app.values["source_layer_name"], "")

    def test_refresh_uses_memory_without_reloading_preferences(self):
        self.activate(Document())
        app.reads.clear()
        with patch.object(docker, "update_settings", wraps=settings.update_settings) as update:
            self.dock._refresh()
            self.dock._refresh()
            update.assert_not_called()
            self.activate(Document())
            update.assert_called_once_with(docker._settings)
        self.assertNotIn("radius", app.reads)
        self.assertNotIn("active", app.reads)

    def test_startup_without_document_resolves_persisted_name_later(self):
        app.values.update(active="True", radius="3.5", source_layer_name="Source")
        docker._settings = settings.load_settings()
        source = Node("Source")
        self.activate(Document([source]))
        self.assertIs(docker._settings.source_layer, source)
        self.assertEqual(self.dock.radius.value(), 3.5)
        self.assertTrue(self.dock.active.isChecked())
        self.assertFalse(app.writes)

    def test_multiple_dockers_share_state_and_one_document_rebind(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.select(source)
        other_dock = self.new_dock()
        self.dock.radius.setValue(9)
        other_dock._refresh()
        self.assertEqual(other_dock.radius.value(), 9)
        replacement = Node("Source")
        app.document = Document([replacement])
        with patch.object(docker, "update_settings", wraps=settings.update_settings) as update:
            self.dock._refresh()
            other_dock._refresh()
            update.assert_called_once()
        self.assertIs(docker._settings.source_layer, replacement)
        self.assertEqual(other_dock.source_layer.currentData(), replacement.id.toString())

    def test_invalid_settings_fall_back_and_false_round_trips(self):
        app.values.update(active="False", radius="nan")
        state = settings.load_settings()
        self.assertFalse(state.active)
        self.assertEqual(state.radius, 1)
        for value in ("0", "-1", "inf", "10001", "invalid"):
            app.values["radius"] = value
            self.assertEqual(settings.load_settings().radius, 1)


if __name__ == "__main__":
    unittest.main()
