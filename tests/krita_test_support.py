"""Krita API doubles; controls, signals and UUIDs use real PyQt6.

Node wrappers share backing state, mirroring Krita's live layer references.
This does not verify SIP conversion of None or Krita's slider rendering.
"""

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from PyQt6.QtCore import QObject, QUuid
from PyQt6.QtWidgets import QDockWidget, QSpinBox

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_stroke_sampler_tests"


class Node:
    def __init__(self, name, children=(), kind="paintlayer"):
        self._state = SimpleNamespace(
            label=name, children=[], kind=kind, uid=QUuid.createUuid(),
            parent=None, child_reads=0,
        )
        for child in children:
            self.add_child(child)

    def wrapper(self):
        result = object.__new__(Node)
        result._state = self._state
        return result

    def __eq__(self, other):
        return isinstance(other, Node) and self._state is other._state

    @property
    def label(self):
        return self._state.label

    @label.setter
    def label(self, name):
        self._state.label = name

    @property
    def children(self):
        return self._state.children

    @property
    def id(self):
        return self._state.uid

    def add_child(self, child):
        child.detach()
        self.children.append(child)
        child._state.parent = self

    def detach(self):
        parent = self._state.parent
        if parent is not None:
            parent.children.remove(self)
        self._state.parent = None

    def childNodes(self):
        self._state.child_reads += 1
        return [node.wrapper() for node in self.children]

    def parentNode(self):
        parent = self._state.parent
        return parent.wrapper() if parent is not None else None

    def name(self):
        return self.label

    def uniqueId(self):
        return self.id

    def type(self):
        return self._state.kind


class Document:
    def __init__(self, children=()):
        self.root = Node("root", children, "grouplayer")
        self.root_reads = 0
        self.id_lookups = []

    def rootNode(self):
        self.root_reads += 1
        return self.root.wrapper()

    def _find(self, predicate, parent=None):
        for node in (parent if parent is not None else self.root).children:
            if predicate(node):
                return node.wrapper()
            found = self._find(predicate, node)
            if found is not None:
                return found
        return None

    def nodeByName(self, name):
        return self._find(lambda node: node.name() == name)

    def nodeByUniqueID(self, uid):
        self.id_lookups.append(uid)
        return self._find(lambda node: node.id == uid)


class Canvas:
    def __init__(self, document):
        self.doc = document

    def view(self):
        return self

    def document(self):
        return self.doc


class Application:
    def __init__(self):
        self.values = {}
        self.writes = []

    def activeDocument(self):
        return None

    def readSetting(self, group, name, default):
        return self.values.get(name, default) or ""

    def writeSetting(self, group, name, value):
        self.writes.append((name, value))
        self.values[name] = value or ""


class SliderSpinBox(QObject):
    def __init__(self):
        super().__init__()
        self._widget = QSpinBox()

    def setRange(self, minimum, maximum):
        self._widget.setRange(minimum, maximum)

    def setExponentRatio(self, ratio):
        pass

    def setBlockUpdateSignalOnDrag(self, blocked):
        pass

    def setValue(self, value):
        self._widget.setValue(value)

    def widget(self):
        return self._widget


app = Application()
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "plugin" / "stroke_sampler")]
sys.modules[PACKAGE] = package
krita = ModuleType("krita")
krita.Krita = SimpleNamespace(instance=lambda: app)
krita.Document, krita.Node, krita.Canvas = Document, Node, Canvas
krita.DockWidget, krita.SliderSpinBox = QDockWidget, SliderSpinBox
with patch.dict(sys.modules, {"krita": krita}):
    settings = importlib.import_module(f"{PACKAGE}.settings")
    layer = importlib.import_module(f"{PACKAGE}.layer")
    state = importlib.import_module(f"{PACKAGE}.state")
    docker = importlib.import_module(f"{PACKAGE}.docker")
