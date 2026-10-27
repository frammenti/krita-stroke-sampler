"""Application wide settings, persisted in the kritarc file."""

from dataclasses import dataclass, field
from typing import Any, TypeVar, Optional, Callable, overload

from krita import Krita, Document, Node

from .layer import get_layer
from .constants import MODULE_ID, DEFAULT_SIZE, DEFAULT_ACTIVE, MIN_SIZE, MAX_SIZE

T = TypeVar("T")


@dataclass
class SamplerSettings:
    _app: Krita = field(repr=False, compare=False)
    active: bool = DEFAULT_ACTIVE
    source_layer: Optional[Node] = None
    size: int = DEFAULT_SIZE

    def _str_or_none(self, value: Any) -> Optional[str]:
        return str(value) if value is not None else None

    def _parse_bool(self, value: str) -> bool:
        normalized = value.strip().lower()
        if normalized in ("true", "1"):
            return True
        if normalized in ("false", "0"):
            return False
        raise ValueError("Invalid boolean setting")

    def _parse_size(self, value: str) -> int:
        size = int(value)
        if not MIN_SIZE <= size <= MAX_SIZE:
            raise ValueError("Sampling size is outside the supported range")
        return size

    @overload
    def read(self, name: str, cast: Callable[[str], T], default: T) -> T: ...

    @overload
    def read(self, name: str, cast: Callable[[str], T]) -> Optional[T]: ...

    def read(
        self, name: str, cast: Callable[[str], T], default: Optional[T] = None
    ) -> Optional[T]:
        value_str = self._app.readSetting(MODULE_ID, name, self._str_or_none(default))
        if not value_str:
            return default
        try:
            return cast(value_str)
        except ValueError, TypeError:
            return default

    def write(self, name: str, value: Any) -> None:
        self._app.writeSetting(MODULE_ID, name, self._str_or_none(value))

    def load(self, document: Optional[Document] = None) -> None:
        """Reload preferences in place."""
        self.active = self.read("active", self._parse_bool, DEFAULT_ACTIVE)
        self.size = self.read("size", self._parse_size, DEFAULT_SIZE)

        if document is not None:
            self.update(document)
        else:
            self.source_layer = None

    def update(self, document: Optional[Document]) -> None:
        """Rebind the source layer on document changes."""
        source_name: Optional[str] = None

        # Prefer the live name
        if self.source_layer is not None:
            try:
                source_name = self.source_layer.name()
            # The previous document may already have destroyed the Qt wrapper.
            except RuntimeError:
                pass

        # Fallback persisted name
        if source_name is None:
            source_name = self.read("source_layer_name", str)

        self.source_layer = get_layer(source_name, document) if source_name else None

    def save(self) -> None:
        """Persist the current state after a user change."""
        source_name = self.source_layer.name() if self.source_layer else None

        self.write("active", self.active)
        self.write("source_layer_name", source_name)
        self.write("size", self.size)
