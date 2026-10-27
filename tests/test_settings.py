"""Global persistence, parsing and document-bound source resolution."""

import unittest
from unittest.mock import Mock

from krita_test_support import Document, Node, app, settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        app.values.clear()
        app.writes.clear()

    def test_defaults_load_without_writes_or_document(self):
        self.assertEqual(settings.load_settings(), settings.SamplerSettings())
        self.assertFalse(app.writes)

    def test_load_parses_preferences_but_defers_layer_resolution(self):
        app.values.update(active="False", size="50", source_layer_name="Source")
        state = settings.load_settings()
        self.assertFalse(state.active)
        self.assertEqual(state.size, 50)
        self.assertIsNone(state.source_layer)
        self.assertFalse(app.writes)

    def test_boolean_parser_accepts_both_values_and_rejects_invalid_text(self):
        for text, expected in (("true", True), ("1", True), (" TRUE ", True),
                               ("false", False), ("0", False), (" False ", False)):
            with self.subTest(text=text):
                self.assertIs(settings.parse_bool(text), expected)
        with self.assertRaises(ValueError):
            settings.parse_bool("maybe")

    def test_size_parser_checks_integer_bounds_without_float_overflow(self):
        for value in (1, 50, 1000):
            self.assertEqual(settings.parse_size(str(value)), value)
        for text in ("0", "-1", "1001", "1.5", "nan", "inf", "invalid", "9" * 400):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    settings.parse_size(text)

    def test_invalid_persisted_values_use_defaults(self):
        app.values.update(active="maybe", size="nan")
        self.assertEqual(settings.load_settings(), settings.SamplerSettings())
        self.assertFalse(app.writes)

    def test_missing_value_casts_default_or_returns_none_without_cast(self):
        self.assertEqual(settings.read_setting("missing", int, 7), 7)
        cast = Mock()
        self.assertIsNone(settings.read_setting("missing", cast))
        cast.assert_not_called()

    def test_conversion_errors_fall_back_but_other_errors_propagate(self):
        app.values["value"] = "text"
        for error in (ValueError, TypeError):
            self.assertEqual(settings.read_setting("value", Mock(side_effect=error), 7), 7)
        with self.assertRaises(RuntimeError):
            settings.read_setting("value", Mock(side_effect=RuntimeError))

    def test_update_resolves_saved_name_in_supplied_document(self):
        app.values["source_layer_name"] = "Source"
        source = Node("Source")
        state = settings.load_settings()
        settings.update_settings(state, Document([source]))
        self.assertEqual(state.source_layer, source)
        self.assertFalse(app.writes)

    def test_update_uses_live_renamed_source_and_keeps_other_preferences(self):
        source, replacement = Node("Source"), Node("Renamed")
        state = settings.SamplerSettings(True, source.wrapper(), 40)
        source.label = "Renamed"
        app.values["source_layer_name"] = "Old persisted name"
        settings.update_settings(state, Document([replacement]))
        self.assertEqual(state.source_layer, replacement)
        self.assertTrue(state.active)
        self.assertEqual(state.size, 40)
        self.assertFalse(app.writes)

    def test_update_falls_back_if_previous_qt_wrapper_is_destroyed(self):
        source = Node("Source")
        broken = Mock()
        broken.name.side_effect = RuntimeError("wrapped object was deleted")
        state = settings.SamplerSettings(source_layer=broken)
        app.values["source_layer_name"] = "Source"
        settings.update_settings(state, Document([source]))
        self.assertEqual(state.source_layer, source)

    def test_no_match_or_no_document_clears_reference_without_writing(self):
        state = settings.SamplerSettings(source_layer=Node("Missing"))
        settings.update_settings(state, Document())
        self.assertIsNone(state.source_layer)
        app.values["source_layer_name"] = "Missing"
        settings.update_settings(state, None)
        self.assertIsNone(state.source_layer)
        self.assertFalse(app.writes)

    def test_mutable_state_saves_live_name_and_none(self):
        source = Node("Source")
        state = settings.SamplerSettings(source_layer=source.wrapper())
        state.active, state.size = True, 50
        source.label = "Renamed"
        settings.save_settings(state)
        self.assertEqual(app.values, {"active": "True", "size": "50", "source_layer_name": "Renamed"})
        state.source_layer = None
        settings.save_settings(state)
        self.assertIn(("source_layer_name", None), app.writes)
        self.assertEqual(app.values["source_layer_name"], "")
