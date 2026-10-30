from math import floor
from typing import Optional, cast

from krita import View
from PyQt6.QtCore import Qt, QEvent, QObject, pyqtSignal, QPointF, pyqtSlot
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QToolButton
from PyQt6.QtGui import QMouseEvent

from .settings import SamplerSettings
from .color import ColorSampler
from .constants import MODULE_ID

NESTED = Qt.FindChildOption.FindChildrenRecursively
CANVAS = "KisOpenGLCanvas2"
BRUSH_TOOL = "KritaShape/KisToolBrush"


class StrokeListener(QObject):
    stroke_start = pyqtSignal(QPointF)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.setObjectName(f"{MODULE_ID}_listener")

    def eventFilter(self, a0: Optional[QObject], a1: Optional[QEvent]) -> bool:
        # TabletPress is synthesized as MouseButtonPress
        if (event := a1) is not None and event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = cast(QMouseEvent, event)
            if mouse_event.button() == Qt.MouseButton.LeftButton:
                self.stroke_start.emit(mouse_event.position())
        return False


class StrokeHandler(QObject):

    def __init__(
        self, window: QMainWindow, view: Optional[View], settings: SamplerSettings
    ) -> None:
        super().__init__(window)
        self.setObjectName(f"{MODULE_ID}_handler")
        self.window = window
        self.view = view
        self.settings = settings

        self.stroke_listener = StrokeListener(self)
        self.stroke_listener.stroke_start.connect(self.atStrokeStart)

        self.color_sampler = ColorSampler()

        self._brush_active = False
        brush = window.findChild(QToolButton, BRUSH_TOOL, NESTED)

        if brush is not None:
            self._brush_active = brush.isChecked()
            brush.toggled.connect(self._brush_toggled)

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self.focusChanged)

        self.viewChanged(view)

    @pyqtSlot(bool)
    def _brush_toggled(self, checked: bool) -> None:
        self._brush_active = checked

    @pyqtSlot(QWidget, QWidget)
    def focusChanged(self, _: Optional[QWidget], widget: Optional[QWidget]) -> None:
        if widget is None or not self.window.isAncestorOf(widget):
            return

        metaobj = widget.metaObject()

        if metaobj is None:
            return

        if metaobj.className() != CANVAS:
            return

        # focusChanged follows FocusIn delivery, where Krita reinstalls its filters.
        # Reinstall ours last so it observes input before those filters.
        widget.installEventFilter(self.stroke_listener)

    def viewChanged(self, view: Optional[View]) -> None:
        self.view = view

        if view is None or self.window is None:
            return

        for widget in self.window.findChildren(QWidget, "", NESTED):
            if (
                metaobj := widget.metaObject()
            ) is not None and metaobj.className() == CANVAS:
                widget.installEventFilter(self.stroke_listener)

    @pyqtSlot(QPointF)
    def atStrokeStart(self, point: QPointF) -> None:
        if (
            self.view is None
            or not self.settings.active
            or not self._brush_active
            or self.settings.source_layer is None
        ):
            return

        canvas_to_flake, invertible = self.view.flakeToCanvasTransform().inverted()

        if not invertible:
            return

        flake_point = canvas_to_flake.map(point)
        image_point = self.view.flakeToImageTransform().map(flake_point)

        color = self.color_sampler.sample_pixel(
            self.settings.source_layer, floor(image_point.x()), floor(image_point.y()), self.settings.size
        )
        if color is not None:
            self.view.setForeGroundColor(color)
