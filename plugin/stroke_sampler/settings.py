"""Application wide settings, persisted in the kritarc file."""

from dataclasses import dataclass
from typing import Any, TypeVar, Optional, Callable, overload

from krita import Document, Node

from .context import app
from .layer import get_layer
from .constants import MODULE_ID, DEFAULT_SIZE, DEFAULT_ACTIVE, MIN_SIZE, MAX_SIZE


@dataclass
class SamplerSettings:
    active: bool = DEFAULT_ACTIVE
    source_layer: Optional[Node] = None
    size: int = DEFAULT_SIZE


def str_or_none(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "1"):
        return True
    if normalized in ("false", "0"):
        return False
    raise ValueError("Invalid boolean setting")


def parse_size(value: str) -> int:
    size = int(value)
    if not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError("Sampling size is outside the supported range")
    return size


T = TypeVar("T")


@overload
def read_setting(name: str, cast: Callable[[str], T], default: T) -> T: ...


@overload
def read_setting(name: str, cast: Callable[[str], T]) -> Optional[T]: ...


def read_setting(
    name: str, cast: Callable[[str], T], default: Optional[T] = None
) -> Optional[T]:
    value_str = app.readSetting(MODULE_ID, name, str_or_none(default))
    if not value_str:
        return default
    try:
        return cast(value_str)
    except ValueError, TypeError:
        return default


def write_setting(name: str, value: Any) -> None:
    app.writeSetting(MODULE_ID, name, str_or_none(value))


def load_settings() -> SamplerSettings:
    """Load once; keep and mutate the returned object for the session."""
    active = read_setting("active", parse_bool, DEFAULT_ACTIVE)
    # Documents are not available when Krita creates the docker at startup.
    source_layer = None
    size = read_setting("size", parse_size, DEFAULT_SIZE)

    return SamplerSettings(active, source_layer, size)


def update_settings(
    settings: SamplerSettings, document: Optional[Document] = None
) -> None:
    """Rebind the source layer on document changes."""
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

    settings.source_layer = get_layer(source_name, document) if source_name else None


def save_settings(settings: SamplerSettings) -> None:
    """Persist the current state after a user change."""
    source_name = settings.source_layer.name() if settings.source_layer else None

    write_setting("active", settings.active)
    write_setting("source_layer_name", source_name)
    write_setting("size", settings.size)
