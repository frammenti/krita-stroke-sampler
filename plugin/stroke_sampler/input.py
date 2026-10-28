from typing import Optional, cast

from krita import Canvas
from PyQt6.QtCore import Qt, QEvent, QObject, pyqtSignal, QPointF, pyqtSlot
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QToolButton
from PyQt6.QtGui import QMouseEvent

from .settings import SamplerSettings

NESTED = Qt.FindChildOption.FindChildrenRecursively
CANVAS = "KisOpenGLCanvas2"
BRUSH_TOOL = "KritaShape/KisToolBrush"


class StrokeListener(QObject):
    stroke_start = pyqtSignal(QWidget, QPointF)

    def __init__(self, parent: QObject):
        super().__init__(parent)

    def eventFilter(self, a0: Optional[QObject], a1: Optional[QEvent]) -> bool:
        # TabletPress is synthesized as MouseButtonPress
        if (
            isinstance(a0, QWidget)
            and (event := a1) is not None
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            mouse_event = cast(QMouseEvent, event)
            if mouse_event.button() == Qt.MouseButton.LeftButton:
                self.stroke_start.emit(a0, mouse_event.position())
        return False


class StrokeHandler(QObject):

    def __init__(
        self, window: QMainWindow, canvas: Optional[Canvas], settings: SamplerSettings
    ) -> None:
        super().__init__(window)
        self.window = window
        self.canvas = canvas
        self.view = canvas.view() if canvas is not None else None
        self.settings = settings
        self.stroke_listener = StrokeListener(self)
        self.stroke_listener.stroke_start.connect(self.atStrokeStart)
        self._brush_active = False

        brush = window.findChild(QToolButton, BRUSH_TOOL, NESTED)

        if brush is not None:
            self._brush_active = brush.isChecked()
            brush.toggled.connect(self._brush_toggled)

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self.focusChanged)

        self.canvasChanged(canvas)

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

    def canvasChanged(self, canvas: Optional[Canvas]) -> None:
        self.canvas = canvas
        self.view = canvas.view() if canvas is not None else None

        if canvas is None or self.window is None:
            return

        for widget in self.window.findChildren(QWidget, "", NESTED):
            metaobj = widget.metaObject()
            if metaobj is None:
                continue
            elif metaobj.className() == CANVAS:
                widget.installEventFilter(self.stroke_listener)

    @pyqtSlot(QWidget, QPointF)
    def atStrokeStart(self, receiver: QWidget, point: QPointF) -> None:
        if not self.settings.active or not self._brush_active:
            return

        print(
            "Receiver:",
            receiver,
            "Canvas:",
            self.canvas,
            "x:",
            point.x(),
            "y:",
            point.y(),
        )

        if self.view is None:
            return

        foreground = self.view.foregroundColor()
        background = self.view.backgroundColor()

        self.view.setForeGroundColor(background)
        self.view.setBackGroundColor(foreground)
