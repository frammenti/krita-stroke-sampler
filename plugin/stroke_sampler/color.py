"""Read a circular projection sample into a color with its original ICC profile."""

import math
from functools import partial
from struct import Struct
from typing import Optional, Callable, Any
from warnings import warn

from krita import ManagedColor, Node

from .constants import MIN_SIZE, MAX_SIZE

try:
    import numpy as np
except ImportError:
    np = None


class ColorSampler:
    CHANNELS = {"RGBA": 4, "GRAYA": 2, "LABA": 4, "CMYKA": 5, "XYZA": 4, "YCbCrA": 4}

    DEPTHS = {
        "U8": ("B", "u1", 255.0),
        "U16": ("H", "=u2", 65535.0),
        "F16": ("e", "=f2", 1.0),
        "F32": ("f", "=f4", 1.0),
    }

    LAB_NORMALIZATION = {
        "U8": (0.0, 128.0, 255.0, 255.0),
        "U16": (0.0, 32896.0, 65535.0, 65535.0),
        "F16": (-128.0, 0.0, 127.0, 100.0),
        "F32": (-128.0, 0.0, 127.0, 100.0),
    }

    def __init__(self):
        self._mask: tuple[int, Any] = (0, [])
        self.presets: dict[tuple[str, str], Callable[..., Optional[list[float]]]] = {}
        for model, count in self.CHANNELS.items():
            for depth, (code, np_type, scale) in self.DEPTHS.items():
                self.presets[(model, depth)] = partial(
                    self._color_values,
                    model=model,
                    depth=depth,
                    layout=Struct(f"={count}{code}"),
                    scale=scale,
                    np_type=np_type,
                )

    def _color_values(
        self,
        pixel: bytes,
        size: int = 1,
        *,
        model: str,
        depth: str,
        layout: Struct,
        scale: float,
        np_type: str,
    ) -> Optional[list[float]]:
        if not pixel or not MIN_SIZE <= size <= MAX_SIZE:
            return None

        expected = layout.size * size * size
        if len(pixel) != expected:
            warn(
                f"Expected {expected} bytes for color model {model}, got {len(pixel)}",
                UserWarning,
            )
            return None

        if size == 1:
            raw = layout.unpack(pixel)

            if raw[-1] <= 0:  # transparent
                return None

        elif np is not None:
            # View the bytes as [row, column, channel], last channel is alpha
            pixels = np.frombuffer(pixel, dtype=np_type).reshape(size, size, -1)

            if self._mask[0] != size:
                # Cache which pixel centers fall inside the sampling circle
                offsets = np.arange(size, dtype=np.float64) - (size - 1) / 2
                self._mask = (
                    size,
                    offsets[:, None] ** 2 + offsets[None, :] ** 2 <= (size / 2) ** 2,
                )

            # Keep only pixels inside the circle with nonzero alpha and finite channels
            valid = (
                self._mask[1] & (pixels[:, :, -1] > 0) & np.isfinite(pixels).all(axis=2)
            )

            if not valid.any():
                return None

            # Boolean indexing drops invalid pixels, :-1 excludes the alpha channel.
            # float64 accumulation avoids integer overflow and half-float loss.
            mean = pixels[valid, :-1].mean(axis=0, dtype=np.float64)
            raw = (*mean.tolist(), scale)

        # Fallback when numpy is not available
        else:
            # Even diameters have the center between pixels, odd diameters have a central pixel
            center = (size - 1) / 2
            radius_squared = (size / 2) ** 2
            sums = [0.0] * (self.CHANNELS[model] - 1)
            count = 0
            data = memoryview(pixel)

            for row in range(size):
                reach = math.sqrt(radius_squared - (row - center) ** 2)
                first = max(0, math.ceil(center - reach))
                last = min(size - 1, math.floor(center + reach))
                start = (row * size + first) * layout.size
                end = (row * size + last + 1) * layout.size

                for sample in layout.iter_unpack(data[start:end]):
                    if not all(math.isfinite(value) for value in sample):
                        continue
                    if sample[-1] <= 0:  # transparent
                        continue

                    for channel in range(len(sums)):
                        sums[channel] += sample[channel]
                    count += 1

            if count == 0:
                return None

            # Average native channel values before Lab's nonlinear encoding.
            raw = (*[value / count for value in sums], scale)

        if not all(math.isfinite(value) for value in raw):
            warn(f"Malformed pixel data {raw}", UserWarning)
            return None

        if model == "LABA":
            # Lab's a/b channels have an asymmetric neutral point
            low, middle, high, lightness = self.LAB_NORMALIZATION[depth]
            values = [
                raw[0] / lightness,
                *[
                    (
                        (value - low) / (2 * (middle - low))
                        if (value := raw[i]) <= middle
                        else 0.5 + (value - middle) / (2 * (high - middle))
                    )
                    for i in (1, 2)
                ],
                raw[-1] / scale,
            ]
        elif model == "CMYKA" and depth.startswith("F"):
            values = [value / 100.0 for value in raw[:4]] + [raw[-1] / scale]
        else:
            values = [value / scale for value in raw]

        values[-1] = 1.0  # restore alpha
        return values

    def sample_pixel(
        self, source: Optional[Node], x: int, y: int, size: int = 1
    ) -> ManagedColor | None:
        """Return an opaque color, or None for empty/transparent/malformed data."""
        if source is None or not MIN_SIZE <= size <= MAX_SIZE:
            return None

        model, depth, profile = (
            source.colorModel(),
            source.colorDepth(),
            source.colorProfile(),
        )

        color_values = self.presets.get((model, depth))

        if color_values is None:
            warn(f'Unknown color model "{model}" or depth "{depth}"', UserWarning)
            return None

        pixel = source.projectionPixelData(
            x - size // 2, y - size // 2, size, size
        ).data()

        values = color_values(pixel, size)

        if values is None:
            return None

        color = ManagedColor(model, depth, profile)
        # Krita can silently fall back if the requested color space is unavailable.
        if (color.colorModel(), color.colorDepth(), color.colorProfile()) != (
            model, depth, profile
        ):
            return None
        color.setComponents(values)

        return color
