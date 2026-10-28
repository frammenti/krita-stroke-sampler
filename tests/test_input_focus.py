"""Restore canvas listener priority after a competing FocusIn filter."""
import unittest
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from krita_test_support import docker


class KisOpenGLCanvas2(QWidget):
    pass


class Probe(QObject):
    def __init__(self, consume=False):
        super().__init__()
        self.consume = consume
        self.count = 0

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn and self.consume:
            obj.installEventFilter(self)
        if event.type() == QEvent.Type.User:
            self.count += 1
            return self.consume
        return False


class FocusTests(unittest.TestCase):
    def test_refocus_restores_priority_without_processing_queued_events(self):
        qt = QApplication.instance() or QApplication([])
        window = QMainWindow()
        central = QWidget()
        window.setCentralWidget(central)
        canvas = KisOpenGLCanvas2(central)
        canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        other = QWidget(central)
        other.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        handler = docker.StrokeHandler(window, None, None)
        probe, competitor = Probe(), Probe(consume=True)
        handler.stroke_listener = probe
        canvas.installEventFilter(probe)
        canvas.installEventFilter(competitor)
        window.show()
        window.activateWindow()
        qt.processEvents()
        try:
            for _ in range(2):
                other.setFocus()
                canvas.setFocus()
                self.assertIs(qt.focusWidget(), canvas)
                before = probe.count
                QApplication.sendEvent(canvas, QEvent(QEvent.Type.User))
                self.assertEqual(probe.count, before + 1)
            QApplication.sendEvent(other, QEvent(QEvent.Type.User))
            self.assertEqual(probe.count, before + 1)
        finally:
            sip.delete(window)
