"""Application wide settings, persisted in the kritarc file."""

from dataclasses import dataclass
import math
from typing import Any, TypeVar, Optional, Callable, overload

from krita import Document, Node

from .context import app
from .constants import MODULE_ID, DEFAULT_RADIUS, DEFAULT_ACTIVE, MIN_RADIUS, MAX_RADIUS


@dataclass
class SamplerSettings:
    active: bool = DEFAULT_ACTIVE
    source_layer: Optional[Node] = None
    radius: float = DEFAULT_RADIUS


def get_layer(name: str) -> Optional[Node]:
    document = app.activeDocument()

    if document is None:
        return None

    layer = Document.nodeByName(document, name)

    # A Krita Node can be either a layer or a mask.
    # The sampler accepts layers, not masks.
    # Possible values are:
    # - paintlayer,
    # - grouplayer,
    # - filelayer,
    # - filterlayer,
    # - filllayer,
    # - clonelayer,
    # - vectorlayer,
    # - transparencymask,
    # - filtermask,
    # - transformmask,
    # - selectionmask,
    # - colorizemask.
    # Reference: https://api.kde.org/legacy/krita/html/classNode.html#a58f4025f31c1bb44df0eb6df7b559e70
    if layer and not layer.type().endswith("layer"):
        return None

    return layer


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "1"):
        return True
    if normalized in ("false", "0"):
        return False
    raise ValueError("Invalid boolean setting")


def parse_radius(value: str) -> float:
    radius = float(value)
    if not math.isfinite(radius) or not MIN_RADIUS <= radius <= MAX_RADIUS:
        raise ValueError("Sampling radius is outside the supported range")
    return radius


T = TypeVar("T")


@overload
def read_setting(name: str, cast: Callable[[str], T], default: T) -> T: ...


@overload
def read_setting(name: str, cast: Callable[[str], T]) -> Optional[T]: ...


def read_setting(
    name: str, cast: Callable[[str], T], default: Optional[T] = None
) -> Optional[T]:
    value_str = app.readSetting(
        MODULE_ID, name, str(default) if default is not None else None
    )
    if not value_str:
        return default
    try:
        return cast(value_str)
    except ValueError, TypeError:
        return default


def write_setting(name: str, value: Any) -> None:
    app.writeSetting(MODULE_ID, name, str(value) if value is not None else None)


def load_settings() -> SamplerSettings:
    """Load once; keep and mutate the returned object for the session."""
    active = read_setting("active", parse_bool, DEFAULT_ACTIVE)
    source_layer = read_setting("source_layer_name", get_layer)
    radius = read_setting("radius", parse_radius, DEFAULT_RADIUS)

    return SamplerSettings(active, source_layer, radius)


def update_settings(settings: SamplerSettings) -> None:
    """Rebind the source on document changes; leave other settings untouched."""
    source_name: Optional[str] = None

    # Prefer the live name
    if settings.source_layer is not None:
        try:
            source_name = settings.source_layer.name()
        # The previous document may already have destroyed the Qt wrapper.
        except RuntimeError:
            pass

    # Fallback persisted name
    if source_name is None:
        source_name = read_setting("source_layer_name", str)

    settings.source_layer = get_layer(source_name) if source_name else None


def save_settings(settings: SamplerSettings) -> None:
    """Persist the current state after a user change."""
    source_name = settings.source_layer.name() if settings.source_layer else None

    write_setting("active", settings.active)
    write_setting("source_layer_name", source_name)
    write_setting("radius", settings.radius)
