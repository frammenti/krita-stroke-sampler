"""Pointer signal payload and window-local brush activation checks."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QToolButton, QWidget

from krita_test_support import docker


class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow()
        self.canvas_widget = QWidget(self.window)
        self.settings = SimpleNamespace(active=True)
        self.button = QToolButton(self.window)
        self.button.setObjectName("KritaShape/KisToolBrush")
        self.button.setCheckable(True)
        self.handler = docker.StrokeHandler(self.window, None, self.settings)
        self.view = Mock()
        self.handler.view = self.view

    def tearDown(self):
        sip.delete(self.window)

    def press(self, button=Qt.MouseButton.LeftButton):
        event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(12, 34),
                            QPointF(12, 34), button, button, Qt.KeyboardModifier.NoModifier)
        return self.handler.stroke_listener.eventFilter(self.canvas_widget, event)

    def test_signal_preserves_receiver_and_local_position_without_consuming_event(self):
        received = []
        self.handler.stroke_listener.stroke_start.connect(lambda *args: received.append(args))
        self.assertFalse(self.press())
        self.assertEqual(received, [(self.canvas_widget, QPointF(12, 34))])
        self.press(Qt.MouseButton.RightButton)
        self.assertEqual(len(received), 1)

    def test_only_selected_brush_swaps_colors(self):
        self.press()
        self.view.setForeGroundColor.assert_not_called()
        self.button.setChecked(True)
        self.press()
        self.view.setForeGroundColor.assert_called_once_with(self.view.backgroundColor.return_value)
        self.view.setBackGroundColor.assert_called_once_with(self.view.foregroundColor.return_value)
        self.view.reset_mock()
        self.button.setChecked(False)
        self.press()
        self.view.setForeGroundColor.assert_not_called()

    def test_disabled_sampler_does_nothing(self):
        self.button.setChecked(True)
        self.settings.active = False
        self.press()
        self.view.setForeGroundColor.assert_not_called()

    def test_missing_brush_button_leaves_handler_inactive(self):
        sip.delete(self.button)
        handler = docker.StrokeHandler(self.window, None, self.settings)
        handler.view = self.view
        handler.atStrokeStart(self.canvas_widget, QPointF())
        self.view.setForeGroundColor.assert_not_called()

    def test_already_selected_brush_is_initialized(self):
        self.button.setChecked(True)
        handler = docker.StrokeHandler(self.window, None, self.settings)
        handler.view = self.view
        handler.atStrokeStart(self.canvas_widget, QPointF())
        self.view.setForeGroundColor.assert_called_once()
        self.button.setChecked(False)
        self.view.reset_mock()
        handler.atStrokeStart(self.canvas_widget, QPointF())
        self.view.setForeGroundColor.assert_not_called()

    def test_cleared_canvas_prevents_color_changes(self):
        self.button.setChecked(True)
        self.handler.canvasChanged(None)
        self.press()
        self.view.setForeGroundColor.assert_not_called()

    def test_brush_changes_are_isolated_between_windows(self):
        other = QMainWindow()
        button = QToolButton(other)
        button.setObjectName("KritaShape/KisToolBrush")
        button.setCheckable(True)
        button.setChecked(True)
        try:
            self.press()
            self.view.setForeGroundColor.assert_not_called()
        finally:
            sip.delete(other)
