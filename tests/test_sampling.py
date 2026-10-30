"""Projection decoding fixtures in Krita's native channel storage formats."""

import struct
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QByteArray

from krita_test_support import sampling


class SamplingTests(unittest.TestCase):
    def setUp(self):
        self.sampler = sampling.ColorSampler()

    def sample(self, model, depth, code, raw):
        node = Mock()
        node.colorModel.return_value = model
        node.colorDepth.return_value = depth
        node.colorProfile.return_value = "source ICC profile"
        node.projectionPixelData.return_value = QByteArray(struct.pack(f"={len(raw)}{code}", *raw))
        color = Mock()
        color.colorModel.return_value = model
        color.colorDepth.return_value = depth
        color.colorProfile.return_value = "source ICC profile"
        with patch.object(sampling, "ManagedColor", return_value=color) as factory:
            result = self.sampler.sample_pixel(node, -2, 7)
        node.projectionPixelData.assert_called_once_with(-2, 7, 1, 1)
        if result is not None:
            factory.assert_called_once_with(model, depth, "source ICC profile")
            self.assertIs(result, color)
            return color.setComponents.call_args.args[0]
        color.setComponents.assert_not_called()
        return None

    def test_integer_rgb_retains_bgra_order_and_makes_sample_opaque(self):
        for depth, code, maximum in [("U8", "B", 255), ("U16", "H", 65535)]:
            with self.subTest(depth=depth):
                self.assertEqual(self.sample("RGBA", depth, code, [0, maximum, 0, 1]),
                                 [0, 1, 0, 1])
                self.assertEqual(self.sample("RGBA", depth, code, [maximum, 0, 0, maximum]),
                                 [1, 0, 0, 1])

    def test_float_rgb_preserves_hdr_and_negative_channels(self):
        for depth, code in [("F16", "e"), ("F32", "f")]:
            self.assertEqual(self.sample("RGBA", depth, code, [2, -0.5, 0.25, 0.5]),
                             [2, -0.5, 0.25, 1])

    def test_gray_xyz_ycbcr_and_integer_cmyk(self):
        for model, raw in [("GRAYA", [255, 255]), ("XYZA", [0, 255, 0, 255]),
                           ("YCbCrA", [255, 0, 255, 255]), ("CMYKA", [0, 255, 0, 255, 255])]:
            self.assertEqual(self.sample(model, "U8", "B", raw), [v / 255 for v in raw])

    def test_lab_neutral_and_chroma_endpoints(self):
        for depth, code, maximum, middle in [("U8", "B", 255, 128), ("U16", "H", 65535, 32896)]:
            self.assertEqual(self.sample("LABA", depth, code, [maximum, middle, middle, maximum]),
                             [1, 0.5, 0.5, 1])
            self.assertEqual(self.sample("LABA", depth, code, [0, 0, maximum, maximum]),
                             [0, 0, 1, 1])
        self.assertEqual(self.sample("LABA", "F32", "f", [50, -64, 63.5, 1]),
                         [0.5, 0.25, 0.75, 1])

    def test_float_cmyk_percentages(self):
        self.assertEqual(self.sample("CMYKA", "F32", "f", [0, 25, 50, 100, 1]),
                         [0, 0.25, 0.5, 1, 1])

    def test_transparent_and_nonfinite_samples_are_ignored(self):
        for raw in [[1, 0, 0, 0], [float("nan"), 0, 0, 1], [float("inf"), 0, 0, 1]]:
            self.assertIsNone(self.sample("RGBA", "F32", "f", raw))

    def test_empty_or_wrong_sized_data_and_unsupported_formats_are_ignored(self):
        node = Mock()
        node.colorModel.return_value = "RGBA"
        node.colorDepth.return_value = "U8"
        for data in [b"", b"\x00", b"\x00" * 8]:
            node.projectionPixelData.return_value = QByteArray(data)
            self.assertIsNone(self.sampler.sample_pixel(node, 0, 0))
        node.colorModel.return_value = "A"
        self.assertIsNone(self.sampler.sample_pixel(node, 0, 0))

    def test_unavailable_color_space_does_not_use_constructor_fallback(self):
        node = Mock()
        node.colorModel.return_value = "RGBA"
        node.colorDepth.return_value = "U8"
        node.colorProfile.return_value = "missing profile"
        node.projectionPixelData.return_value = QByteArray(b"\xff" * 4)
        with patch.object(sampling, "ManagedColor") as factory:
            self.assertIsNone(self.sampler.sample_pixel(node, 0, 0))
            factory.return_value.setComponents.assert_not_called()

    def test_presets_keep_independent_formats_when_interleaved(self):
        rgb = self.sampler.presets[("RGBA", "U8")]
        lab = self.sampler.presets[("LABA", "F32")]
        cmyk = self.sampler.presets[("CMYKA", "F16")]
        for _ in range(2):
            self.assertEqual(rgb(bytes([255, 0, 0, 128])), [1, 0, 0, 1])
            self.assertEqual(lab(struct.pack("=4f", 50, 0, 0, 1)), [0.5, 0.5, 0.5, 1])
            self.assertEqual(cmyk(struct.pack("=5e", 0, 25, 50, 100, 1)), [0, 0.25, 0.5, 1, 1])

    def test_circular_mask_excludes_square_corners(self):
        red = bytes([0, 0, 255, 255])
        blue = bytes([255, 0, 0, 255])
        pixels = [red] * 25
        for i in (0, 4, 20, 24):
            pixels[i] = blue
        self.assertEqual(self.sampler.presets[("RGBA", "U8")](b"".join(pixels), 5),
                         [0, 0, 1, 1])

    def test_even_diameter_ignores_alpha_weights_and_transparent_colors(self):
        pixels = bytes([0, 0, 255, 255, 255, 0, 0, 85,
                        0, 255, 0, 0, 255, 255, 255, 0])
        self.assertEqual(self.sampler.presets[("RGBA", "U8")](pixels, 2),
                         [0.5, 0, 0.5, 1])

    def test_lab_averages_native_channels_before_normalization(self):
        pixels = struct.pack("=16f", *([50, -64, 0, 1, 50, 63.5, 0, 1] * 2))
        values = self.sampler.presets[("LABA", "F32")](pixels, 2)
        self.assertEqual(values, [0.5, 127.75 / 256, 0.5, 1])

    def test_area_preserves_hdr_and_ignores_nonfinite_pixels(self):
        pixels = struct.pack("=16f", 4, -1, 0, 1, 2, 0, 0, 1,
                             float("nan"), 1, 1, 1, 1, 1, 1, 0)
        self.assertEqual(self.sampler.presets[("RGBA", "F32")](pixels, 2),
                         [3, -0.5, 0, 1])

    def test_area_supports_all_formats_and_preserves_uniform_color(self):
        for (model, depth), convert in self.sampler.presets.items():
            with self.subTest(model=model, depth=depth):
                code, _, scale = self.sampler.DEPTHS[depth]
                count = self.sampler.CHANNELS[model]
                raw = [int(scale)] * count
                pixel = struct.pack(f"={count}{code}", *raw)
                self.assertEqual(convert(pixel), convert(pixel * 25, 5))
                self.assertIsNone(convert(bytes(len(pixel) * 25), 5))

    def test_area_reads_one_centered_rectangle_with_negative_coordinates(self):
        node = Mock()
        node.colorModel.return_value = "RGBA"
        node.colorDepth.return_value = "U8"
        node.colorProfile.return_value = "source ICC profile"
        for size, expected in [(1, (-2, 7, 1, 1)), (2, (-3, 6, 2, 2)), (5, (-4, 5, 5, 5))]:
            node.projectionPixelData.reset_mock()
            node.projectionPixelData.return_value = QByteArray(bytes(4 * size * size))
            self.assertIsNone(self.sampler.sample_pixel(node, -2, 7, size))
            node.projectionPixelData.assert_called_once_with(*expected)

    def test_area_rejects_truncated_buffer(self):
        with self.assertWarns(UserWarning):
            self.assertIsNone(self.sampler.presets[("RGBA", "U8")](bytes(15), 2))

    @unittest.skipIf(sampling.np is None, "NumPy is not installed")
    def test_vectorized_and_fallback_match_for_all_formats(self):
        import random
        rng = random.Random(42)
        for (model, depth), convert in self.sampler.presets.items():
            for size in (2, 5, 6):
                with self.subTest(model=model, depth=depth, size=size):
                    code, _, scale = self.sampler.DEPTHS[depth]
                    count = self.sampler.CHANNELS[model]
                    raw = []
                    for i in range(size * size):
                        channels = [rng.randint(0, int(scale)) if depth.startswith("U")
                                    else rng.uniform(-100, 100) for _ in range(count - 1)]
                        alpha = (0, 1, int(scale))[i % 3]
                        raw.extend(channels + [alpha])
                    pixel = struct.pack(f"={len(raw)}{code}", *raw)
                    expected = convert(pixel, size)
                    with patch.object(sampling, "np", None):
                        actual = convert(pixel, size)
                    for a, b in zip(actual, expected):
                        self.assertAlmostEqual(a, b, places=12)

    def test_size_limit_is_enforced_before_reading(self):
        node = Mock()
        for size in (-1, 0, 1001):
            self.assertIsNone(self.sampler.sample_pixel(node, 0, 0, size))
        node.projectionPixelData.assert_not_called()

    @unittest.skipIf(sampling.np is None, "NumPy is not installed")
    def test_mask_cache_reuses_size_across_formats_and_rebuilds_on_resize(self):
        rgb = self.sampler.presets[("RGBA", "U8")]
        gray = self.sampler.presets[("GRAYA", "U16")]
        rgb(bytes([0, 0, 255, 255]) * 25, 5)
        first = self.sampler._mask[1]
        self.assertEqual(first.shape, (5, 5))
        self.assertEqual(int(first.sum()), 21)
        gray(struct.pack("=2H", 65535, 65535) * 25, 5)
        self.assertIs(self.sampler._mask[1], first)
        rgb(bytes([0, 0, 255, 255]) * 4, 2)
        self.assertEqual(self.sampler._mask[0], 2)
        self.assertEqual(self.sampler._mask[1].shape, (2, 2))
        rgb(bytes([0, 0, 255, 255]) * 25, 5)
        self.assertTrue(sampling.np.array_equal(self.sampler._mask[1], first))

    @unittest.skipIf(sampling.np is None, "NumPy is not installed")
    def test_maximum_diameter_is_supported(self):
        size = 1000
        values = self.sampler.presets[("RGBA", "U8")](bytes([0, 0, 255, 255]) * size**2, size)
        self.assertEqual(values, [0, 0, 1, 1])

    def test_source_metadata_is_refreshed_between_samples(self):
        node = Mock()
        node.colorModel.return_value = "GRAYA"
        node.colorDepth.return_value = "U8"
        node.colorProfile.return_value = "first profile"
        node.projectionPixelData.return_value = QByteArray(bytes([255, 255]))
        with patch.object(sampling, "ManagedColor") as factory:
            color = factory.return_value
            color.colorModel.return_value = "GRAYA"
            color.colorDepth.return_value = "U8"
            color.colorProfile.return_value = "first profile"
            self.assertIs(self.sampler.sample_pixel(node, 0, 0), color)
            node.colorDepth.return_value = "U16"
            node.colorProfile.return_value = "second profile"
            node.projectionPixelData.return_value = QByteArray(struct.pack("=2H", 65535, 65535))
            color.colorDepth.return_value = "U16"
            color.colorProfile.return_value = "second profile"
            self.assertIs(self.sampler.sample_pixel(node, 0, 0), color)
            factory.assert_called_with("GRAYA", "U16", "second profile")
