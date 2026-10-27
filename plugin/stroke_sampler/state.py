"""Shared application and sampler settings for the plugin session."""

from krita import Krita

from .settings import SamplerSettings


def instance() -> Krita:
    instance = Krita.instance()

    if instance is None:
        raise RuntimeError("Krita instance not found")

    return instance


app: Krita = instance()

settings = SamplerSettings(app)
settings.load(app.activeDocument())
