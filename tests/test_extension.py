"""Per-window handler creation and initial canvas attachment."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from krita_test_support import app, docker, extension


class KisOpenGLCanvas2(QWidget):
    pass


class ExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow()
        self.dock = docker.StrokeSamplerDocker()
        self.dock.setParent(self.window)
        self.dock.setObjectName("stroke_sampler")
        self.extension = extension.StrokeSamplerExtension(app)
        self.kwindow = SimpleNamespace(qwindow=lambda: self.window)

    def tearDown(self):
        sip.delete(self.extension)
        sip.delete(self.window)

    def test_creates_handler_with_current_canvas_only_once(self):
        canvas = Mock()
        with (patch.object(self.dock, "canvas", return_value=canvas, create=True),
              patch.object(extension, "StrokeHandler") as factory):
            self.extension.createActions(self.kwindow)
            factory.assert_called_once_with(self.window, canvas, self.dock.settings)
            self.assertIs(self.dock.handler, factory.return_value)
            with self.assertWarnsRegex(RuntimeWarning, "already initialized"):
                self.extension.createActions(self.kwindow)
            self.assertEqual(factory.call_count, 1)

    def test_missing_window_or_docker_is_harmless(self):
        with patch.object(extension, "StrokeHandler") as factory:
            self.extension.createActions(None)
            self.extension.createActions(SimpleNamespace(qwindow=lambda: None))
            self.dock.setObjectName("unrelated")
            self.extension.createActions(self.kwindow)
            factory.assert_not_called()

    def test_initial_canvas_installs_filter_in_own_window(self):
        own = KisOpenGLCanvas2(self.window)
        unrelated = QWidget(self.window)
        other_window = QMainWindow()
        other = KisOpenGLCanvas2(other_window)
        canvas = Mock()
        try:
            handler = docker.StrokeHandler(self.window, canvas, self.dock.settings)
            received = []
            handler.stroke_listener.stroke_start.connect(lambda widget, point: received.append(widget))
            for widget in (own, unrelated, other):
                event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(), QPointF(),
                                    Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                    Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(widget, event)
            self.assertEqual(received, [own])
            self.assertIs(handler.canvas, canvas)
            self.assertIs(handler.view, canvas.view.return_value)
        finally:
            sip.delete(other_window)
