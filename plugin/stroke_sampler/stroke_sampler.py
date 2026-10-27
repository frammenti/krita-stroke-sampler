"""Register one Stroke Sampler docker per Krita window."""

from krita import DockWidgetFactory, DockWidgetFactoryBase

from .docker import StrokeSamplerDocker
from .context import app
from .constants import MODULE_ID

app.addDockWidgetFactory(
    DockWidgetFactory(
        MODULE_ID,
        DockWidgetFactoryBase.DockPosition.DockRight,
        StrokeSamplerDocker,
    )
)
