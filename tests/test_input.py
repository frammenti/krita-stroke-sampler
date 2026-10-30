"""Pointer signal payload and window-local brush activation checks."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QTransform
from PyQt6.QtWidgets import QApplication, QMainWindow, QToolButton, QWidget

from krita_test_support import docker, sampling


class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow()
        self.canvas_widget = QWidget(self.window)
        self.settings = SimpleNamespace(active=True, source_layer=Mock(), size=1)
        self.button = QToolButton(self.window)
        self.button.setObjectName("KritaShape/KisToolBrush")
        self.button.setCheckable(True)
        self.handler = docker.StrokeHandler(self.window, None, self.settings)
        self.view = Mock()
        self.handler.view = self.view
        self.view.flakeToCanvasTransform.return_value = QTransform()
        self.view.flakeToImageTransform.return_value = QTransform()
        self.sampler_patch = patch.object(sampling.ColorSampler, "sample_pixel")
        self.sample = self.sampler_patch.start()
        self.addCleanup(self.sampler_patch.stop)

    def tearDown(self):
        sip.delete(self.window)

    def press(self, button=Qt.MouseButton.LeftButton):
        event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(12, 34),
                            QPointF(12, 34), button, button, Qt.KeyboardModifier.NoModifier)
        return self.handler.stroke_listener.eventFilter(self.canvas_widget, event)

    def test_signal_preserves_local_position_without_consuming_event(self):
        received = []
        self.handler.stroke_listener.stroke_start.connect(lambda *args: received.append(args))
        self.assertFalse(self.press())
        self.assertEqual(received, [(QPointF(12, 34),)])
        self.press(Qt.MouseButton.RightButton)
        self.assertEqual(len(received), 1)

    def test_only_selected_brush_samples_color(self):
        self.press()
        self.view.setForeGroundColor.assert_not_called()
        self.button.setChecked(True)
        self.press()
        self.view.setForeGroundColor.assert_called_once_with(self.sample.return_value)
        self.view.setBackGroundColor.assert_not_called()
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
        handler.atStrokeStart(QPointF())
        self.view.setForeGroundColor.assert_not_called()

    def test_already_selected_brush_is_initialized(self):
        self.button.setChecked(True)
        handler = docker.StrokeHandler(self.window, None, self.settings)
        handler.view = self.view
        handler.atStrokeStart(QPointF())
        self.view.setForeGroundColor.assert_called_once()
        self.button.setChecked(False)
        self.view.reset_mock()
        handler.atStrokeStart(QPointF())
        self.view.setForeGroundColor.assert_not_called()

    def test_cleared_canvas_prevents_color_changes(self):
        self.button.setChecked(True)
        self.handler.viewChanged(None)
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

    def test_floors_image_coordinates_and_passes_size(self):
        self.button.setChecked(True)
        self.view.flakeToCanvasTransform.return_value = QTransform.fromTranslate(10, 20)
        self.view.flakeToImageTransform.return_value = QTransform.fromScale(0.5, 0.5)
        self.settings.size = 5
        self.handler.atStrokeStart(QPointF(9.5, 25.5))
        self.sample.assert_called_once_with(self.settings.source_layer, -1, 2, 5)

    def test_empty_sample_preserves_foreground(self):
        self.button.setChecked(True)
        self.sample.return_value = None
        self.press()
        self.view.setForeGroundColor.assert_not_called()

    def test_missing_source_or_singular_transform_does_not_sample(self):
        self.button.setChecked(True)
        self.settings.source_layer = None
        self.press()
        self.sample.assert_not_called()
        self.settings.source_layer = Mock()
        self.view.flakeToCanvasTransform.return_value = QTransform.fromScale(0, 0)
        self.press()
        self.sample.assert_not_called()
