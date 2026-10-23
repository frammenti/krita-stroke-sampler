from krita import Canvas, DockWidget, Document, Node
from PyQt6.QtCore import QSignalBlocker, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from .context import app
from .settings import load_settings, save_settings, update_settings
from .constants import WINDOW_NAME, MIN_RADIUS, MAX_RADIUS

# One mutable state for the application, shared by dockers in every window.
_settings = load_settings()
_settings_document = app.activeDocument()


class StrokeSamplerDocker(DockWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_NAME)
        self._document: Document | None = None
        self._layer_items: list[tuple[str, str]] = []
        self._nodes: dict[str, Node] = {}

        self._panel = QWidget(self)
        layout = QFormLayout(self._panel)
        self.active = QCheckBox("Enable stroke sampling", self._panel)
        layout.addRow(self.active)

        self.source_layer = QComboBox(self._panel)
        self.source_layer.setToolTip(
            "Layer whose colors will be sampled at stroke start. "
            "Its name is used to select a source when switching documents."
        )
        layout.addRow("Source layer:", self.source_layer)

        self.radius = QDoubleSpinBox(self._panel)
        self.radius.setRange(MIN_RADIUS, MAX_RADIUS)
        self.radius.setDecimals(2)
        self.radius.setSuffix(" px")
        self.radius.setKeyboardTracking(False)
        self.radius.setToolTip(
            "Sampling radius in image pixels, independent of canvas zoom. "
            "Krita's brush size is a diameter; a 1 px radius spans 2 px."
        )
        layout.addRow("Sampling radius:", self.radius)
        self.setWidget(self._panel)

        self.active.toggled.connect(self._active_changed)
        self.source_layer.currentIndexChanged.connect(self._source_changed)
        self.radius.valueChanged.connect(self._radius_changed)
        # Krita's Python API has no layer-tree change signal. Poll only while
        # visible, and rebuild the list only when names, order or IDs change.
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh_if_visible)
        self._timer.start()
        self._refresh()

    def canvasChanged(self, canvas: Canvas | None) -> None:
        self._refresh()

    def _refresh_if_visible(self) -> None:
        if self.isVisible():
            self._refresh()

    def _layers(self, parent: Node, depth: int = 0) -> list[tuple[str, str]]:
        items = []
        # childNodes returns bottom-to-top order; match the Layers docker.
        for node in reversed(parent.childNodes()):
            if node.type().endswith("layer"):
                node_id = node.uniqueId().toString()
                self._nodes[node_id] = node
                items.append(("    " * depth + node.name(), node_id))
                items.extend(self._layers(node, depth + 1))
        return items

    def _refresh(self) -> None:
        global _settings_document

        # Match settings.get_layer(): global state follows the active document,
        # including when several windows have visible dockers.
        document = app.activeDocument()
        if document != _settings_document:
            update_settings(_settings)
            _settings_document = document

        changed_document = document != self._document
        self._document = document
        self.source_layer.setEnabled(document is not None)
        root = document.rootNode() if document is not None else None
        self._nodes = {}
        items = self._layers(root) if root is not None else []
        source_id = None
        if _settings.source_layer is not None:
            try:
                source_id = _settings.source_layer.uniqueId().toString()
            except RuntimeError:
                pass
            if source_id not in self._nodes:
                _settings.source_layer = None
                source_id = None
                save_settings(_settings)
            elif not changed_document:
                old_labels = {node_id: label for label, node_id in self._layer_items}
                new_labels = {node_id: label for label, node_id in items}
                old_label = old_labels.get(source_id)
                new_label = new_labels.get(source_id)
                if old_label is not None and old_label != new_label:
                    # Keep the live node through renames and persist its new name.
                    save_settings(_settings)

        with (
            QSignalBlocker(self.active),
            QSignalBlocker(self.source_layer),
            QSignalBlocker(self.radius),
        ):
            self.active.setChecked(_settings.active)
            if (
                changed_document
                or items != self._layer_items
                or not self.source_layer.count()
            ):
                self._layer_items = items
                self.source_layer.clear()
                self.source_layer.addItem("Select a source layer…", None)
                for label, layer_id in items:
                    self.source_layer.addItem(label, layer_id)
            index = self.source_layer.findData(source_id) if source_id else 0
            self.source_layer.setCurrentIndex(max(index, 0))
            if not self.radius.hasFocus():
                self.radius.setValue(_settings.radius)

    def _active_changed(self, active: bool) -> None:
        self._refresh()
        _settings.active = active
        save_settings(_settings)
        self._refresh()

    def _source_changed(self, index: int) -> None:
        if app.activeDocument() != self._document:
            self._refresh()
            return
        # Capture the ID before refreshing: a layer edit may change list order.
        source_id = self.source_layer.itemData(index)
        self._refresh()
        _settings.source_layer = self._nodes.get(source_id)
        save_settings(_settings)
        self._refresh()

    def _radius_changed(self, radius: float) -> None:
        self._refresh()
        _settings.radius = radius
        save_settings(_settings)
        self._refresh()
