"""Sampler controls and lightweight synchronization with the current document."""

from typing import Optional, cast

from krita import Canvas, DockWidget, Document, SliderSpinBox, Node
from PyQt6.QtCore import QSignalBlocker, QTimer
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFrame, QSpinBox, QFormLayout, QWidget

from .settings import load_settings, save_settings, update_settings
from .layer import is_layer
from .constants import (
    WINDOW_NAME,
    MIN_SIZE,
    MAX_SIZE,
    SIZE_LABEL,
    SIZE_DESCRIPTION,
    ACTIVE_LABEL,
    SOURCE_LAYER_LABEL,
    SOURCE_LAYER_DESCRIPTION,
    SOURCE_LAYER_PLACEHOLDER,
)


class ActiveWidget(QCheckBox):
    def __init__(self, parent: StrokeSamplerDocker):
        super().__init__(ACTIVE_LABEL, parent._widget)
        self._settings = parent._settings
        self.toggled.connect(self._on_input)

    def _on_input(self, value: bool) -> None:
        self._settings.active = value
        save_settings(self._settings)

    def update_value(self) -> None:
        # Programmatic refreshes must not persist settings during startup
        with QSignalBlocker(self):
            self.setChecked(self._settings.active)


class SizeWidget(SliderSpinBox):
    def __init__(self, parent: StrokeSamplerDocker) -> None:
        super().__init__()
        self.setParent(parent._widget)
        self.setRange(MIN_SIZE, MAX_SIZE)
        self.setExponentRatio(3.0)
        self.setBlockUpdateSignalOnDrag(True)

        self._widget: QSpinBox = cast(QSpinBox, self.widget())
        self._widget.setPrefix(f"{SIZE_LABEL}: ")
        self._widget.setSuffix(" px")
        self._widget.setKeyboardTracking(False)
        self._widget.setToolTip(SIZE_DESCRIPTION)

        self._settings = parent._settings
        self._widget.valueChanged.connect(self._on_input)

    def _on_input(self, value: int) -> None:
        self._settings.size = value
        save_settings(self._settings)

    def update_value(self) -> None:
        # valueChanged belongs to the embedded spin box, not Krita's wrapper
        with QSignalBlocker(self._widget):
            if not self._widget.hasFocus():
                self.setValue(self._settings.size)


class SourceLayerWidget(QComboBox):
    def __init__(self, parent: StrokeSamplerDocker):
        super().__init__(parent._widget)
        self._settings = parent._settings
        self._document = parent._document
        self.setToolTip(SOURCE_LAYER_DESCRIPTION)
        self.currentIndexChanged.connect(self._on_input)

        # Poll selected layer for rename, nesting or deletion events
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_selected_layer_name)
        self._timer.start()

    def _label(self, name: str, depth: int) -> str:
        return "    " * depth + name

    def _depth(self, node: Node, root: Node, depth: int = -1) -> int:
        """
        Depth starts at -1 to account for root.
        Returns -1 if the node was deleted.
        """
        parent = node.parentNode()
        if parent:
            return self._depth(parent, root, depth + 1)
        elif node.uniqueId() == root.uniqueId():
            return depth
        else:
            return -1

    def _on_input(self, index: int) -> None:
        if self._document is None:
            return

        if index > 0:
            # The list stores comparable IDs, the node is resolved on selection
            layer_id = self.itemData(index)
            self._settings.source_layer = self._document.nodeByUniqueID(layer_id)
        else:
            self._settings.source_layer = None

        save_settings(self._settings)

    def _update_selected_layer_name(self) -> None:
        if self._document is None or not self.isVisible():
            return

        current = self._settings.source_layer

        if current is None:
            return

        root = self._document.rootNode()

        if root is None:
            return

        current_depth = self._depth(current, root)

        # Layer (or its group) was deleted
        if current_depth == -1:
            # Clear selection even with signal blocked by `showPopup()`
            self._settings.source_layer = None
            save_settings(self._settings)
            with QSignalBlocker(self):
                self.setCurrentIndex(0)
            return

        current_label = self._label(current.name(), current_depth)

        # Layer was renamed or nested
        if self.currentText() != current_label:
            self.setItemText(self.currentIndex(), current_label)
            save_settings(self._settings)

    def _append_layers(self, parent: Node, depth: int = 0) -> None:
        # childNodes returns bottom-to-top order
        for node in reversed(parent.childNodes()):
            if is_layer(node):
                self.addItem(self._label(node.name(), depth), node.uniqueId())
                self._append_layers(node, depth + 1)

    def update_value(self) -> None:
        document = self._document

        # Rebuild the list without triggering any input
        with QSignalBlocker(self):
            self.setEnabled(document is not None)

            self.clear()
            self.addItem(SOURCE_LAYER_PLACEHOLDER, None)

            root = document.rootNode() if document is not None else None
            if root:
                self._append_layers(root)

            current = self._settings.source_layer
            current_index = self.findData(current.uniqueId()) if current else 0
            self.setCurrentIndex(max(current_index, 0))

    def showPopup(self) -> None:
        self._timer.stop()
        # Persist a rename before rebuilding replaces the old label
        self._update_selected_layer_name()
        self.update_value()
        super().showPopup()

    def hidePopup(self) -> None:
        super().hidePopup()
        self._timer.start()


class DockerLayout(QFormLayout):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        # Krita resets the widget margins to 1, 1, 1, 1 after creation,
        # so we set them on the docker.
        parent.setContentsMargins(3, 9, 3, 9)  # left, top, right, bottom
        self.setContentsMargins(1, 1, 1, 1)
        self.setVerticalSpacing(12)

        left, top, right, bottom = self.getContentsMargins()
        print("Left:", left, "Top:", top, "Right:", right, "Bottom:", bottom)

        self._separator = QFrame(parent)
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setFrameShadow(QFrame.Shadow.Sunken)

    def addSeparator(self):
        self.addRow(self._separator)


class StrokeSamplerDocker(DockWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_NAME)

        self._widget = QWidget(self)
        layout = DockerLayout(self._widget)
        self.setWidget(self._widget)

        self._document: Optional[Document] = None
        self._settings = load_settings()

        self.active = ActiveWidget(self)
        layout.addRow(self.active)

        layout.addSeparator()

        self.source_layer = SourceLayerWidget(self)
        layout.addRow(f"{SOURCE_LAYER_LABEL}:", self.source_layer)

        self.sample_size = SizeWidget(self)
        layout.addRow(self.sample_size._widget)

        self.active.update_value()
        self.source_layer.update_value()
        self.sample_size.update_value()

    def _update_document(self, document: Optional[Document]) -> None:
        self._document = document
        self.source_layer._document = document

    def canvasChanged(self, canvas: Optional[Canvas]) -> None:
        # Use this docker's canvas
        document = None

        if canvas:
            view = canvas.view()
            if view:
                document = view.document()

        if document != self._document:
            self._update_document(document)
            update_settings(self._settings, self._document)
            self.source_layer.update_value()
