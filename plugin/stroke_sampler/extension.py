from warnings import warn

from krita import Krita, Extension
from PyQt6.QtCore import Qt

from .docker import StrokeSamplerDocker
from .input import StrokeHandler
from .constants import MODULE_ID

IMMEDIATE = Qt.FindChildOption.FindDirectChildrenOnly


class StrokeSamplerExtension(Extension):

    def __init__(self, app: Krita):
        super().__init__(app)

    def setup(self):
        pass

    def createActions(self, window):
        if window is None:
            return

        main_window = window.qwindow()

        if main_window is None:
            return

        docker = main_window.findChild(StrokeSamplerDocker, MODULE_ID, IMMEDIATE)

        if docker is None:
            return

        if docker.handler is None:
            view = canvas.view() if (canvas := docker.canvas()) is not None else None

            docker.handler = StrokeHandler(main_window, view, docker.settings)
        else:
            warn("The docker handler was already initialized", RuntimeWarning)
