"""Regression tests for the flat layer selector and embedded Qt controls."""

import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QListView

from krita_test_support import Canvas, Document, Node, app, docker


class DockerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        app.values.clear()
        app.values.update(active="False", size="25", source_layer_name="Source")
        app.writes.clear()
        self.dock = docker.StrokeSamplerDocker()
        self.dock.resize(450, 200)
        self.dock.show()
        self.qt.processEvents()
        self.combo = self.dock.source_layer

    def tearDown(self):
        self.combo.hidePopup()
        self.combo._timer.stop()
        self.dock.close()
        self.dock.deleteLater()
        self.qt.processEvents()

    def activate(self, document):
        self.dock.canvasChanged(Canvas(document) if document else None)

    def choose(self, node, keyboard=False):
        self.combo.showPopup()
        self.qt.processEvents()
        row = self.combo.findData(node.id)
        self.assertGreater(row, 0)
        view = self.combo.view()
        index = self.combo.model().index(row, 0)
        if keyboard:
            view.setCurrentIndex(index)
            QTest.keyClick(view, Qt.Key.Key_Return)
        else:
            QTest.qWait(200)
            QTest.mouseClick(
                view.viewport(),
                Qt.MouseButton.LeftButton,
                pos=view.visualRect(index).center(),
            )
        self.qt.processEvents()

    def test_dockers_load_preferences_into_independent_settings(self):
        self.dock.active.setChecked(True)
        self.dock.sample_size._widget.setValue(37)
        other = docker.StrokeSamplerDocker()
        try:
            self.assertIsNot(other.settings, self.dock.settings)
            self.assertTrue(other.active.isChecked())
            self.assertEqual(other.sample_size._widget.value(), 37)
            other.active.setChecked(False)
            other.sample_size._widget.setValue(42)
            self.assertTrue(self.dock.settings.active)
            self.assertEqual(self.dock.settings.size, 37)
            self.assertEqual(app.values["size"], "42")
        finally:
            other.source_layer._timer.stop()
            other.deleteLater()

    def test_every_canvas_notification_reaches_handler(self):
        self.dock.handler = Mock()
        document = Document([Node("Source")])
        first, second = Canvas(document), Canvas(document)
        for canvas in (first, second, None):
            self.dock.canvasChanged(canvas)
            self.dock.handler.viewChanged.assert_called_with(canvas.view() if canvas else None)
        self.assertEqual(self.dock.handler.viewChanged.call_count, 3)

    def test_startup_refresh_does_not_erase_persisted_source(self):
        self.assertFalse(app.writes)
        self.assertEqual(app.values["source_layer_name"], "Source")
        self.assertEqual(self.dock.sample_size._widget.value(), 25)
        self.assertFalse(self.combo.isEnabled())
        source = Node("Source")
        self.activate(Document([source]))
        self.assertEqual(self.combo.currentData(), source.id)
        self.assertFalse(app.writes)

    def test_flat_list_indents_groups_excludes_masks_and_stores_ids(self):
        source = Node("Source")
        group = Node("Group", [source], "grouplayer")
        self.activate(Document([group, Node("Mask", kind="transparencymask")]))
        self.assertIsInstance(self.combo.view(), QListView)
        self.assertEqual(
            [self.combo.itemText(i) for i in range(self.combo.count())],
            ["None", "Group", "    Source"],
        )
        self.assertEqual(self.combo.currentData(), source.id)
        self.assertEqual(self.combo.currentText(), "    Source")
        self.assertEqual(self.combo.itemData(2), source.id)

    def test_rebuild_restores_selection_across_distinct_live_wrappers(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.assertIsNot(self.dock.settings.source_layer, source)
        source.label = "Renamed"
        self.assertEqual(self.dock.settings.source_layer.name(), "Renamed")
        self.combo.update_value()
        self.assertEqual(self.combo.currentData(), source.id)
        self.assertFalse(app.writes)

    def test_mouse_selects_correct_duplicate_and_looks_up_only_on_input(self):
        first, second = Node("Same"), Node("Same")
        doc = Document(
            [Node("A", [first], "grouplayer"), Node("B", [second], "grouplayer")]
        )
        self.activate(doc)
        self.choose(second)
        self.assertEqual(self.dock.settings.source_layer, second)
        self.assertEqual(self.combo.currentData(), second.id)
        self.assertEqual(doc.id_lookups, [second.id])
        self.assertEqual(len(app.writes), 3)
        self.assertFalse(self.combo.view().isVisible())

    def test_keyboard_selection_and_escape_without_save(self):
        source = Node("Colors")
        self.activate(Document([Node("Group", [source], "grouplayer")]))
        self.choose(source, keyboard=True)
        self.assertEqual(self.dock.settings.source_layer, source)
        app.writes.clear()
        self.combo.showPopup()
        QTest.keyClick(self.combo.view(), Qt.Key.Key_Escape)
        self.assertEqual(self.combo.currentData(), source.id)
        self.assertFalse(app.writes)

    def test_poll_rename_does_not_traverse_layer_tree_or_resolve_id(self):
        source = Node("Source")
        doc = Document([source])
        self.activate(doc)
        child_reads = doc.root._state.child_reads
        source.label = "Renamed"
        self.combo._update_selected_layer_name()
        self.assertEqual(self.combo.currentText(), "Renamed")
        self.assertEqual(app.values["source_layer_name"], "Renamed")
        self.assertEqual(doc.root._state.child_reads, child_reads)
        self.assertFalse(doc.id_lookups)
        app.writes.clear()
        self.combo._update_selected_layer_name()
        self.assertFalse(app.writes)

    def test_poll_updates_indentation_after_reparenting(self):
        source, group = Node("Source"), Node("Group", kind="grouplayer")
        self.activate(Document([source, group]))
        group.add_child(source)
        self.combo._update_selected_layer_name()
        self.assertEqual(self.combo.currentText(), "    Source")
        self.assertEqual(self.dock.settings.source_layer, source)

    def test_selected_layer_deletion_clears_and_saves(self):
        source = Node("Source")
        self.activate(Document([source]))
        source.detach()
        self.combo._update_selected_layer_name()
        self.assertIsNone(self.dock.settings.source_layer)
        self.assertIsNone(self.combo.currentData())
        self.assertEqual(app.values["source_layer_name"], "")

    def test_deleted_source_clears_even_if_rebuild_already_selected_none(self):
        source = Node("Source")
        self.activate(Document([source]))
        source.detach()
        self.combo.update_value()
        self.assertEqual(self.combo.currentIndex(), 0)
        self.combo._update_selected_layer_name()
        self.assertIsNone(self.dock.settings.source_layer)
        self.assertEqual(app.values["source_layer_name"], "")

    def test_deleting_enclosing_group_detects_detached_descendant(self):
        source = Node("Source")
        group = Node("Group", [source], "grouplayer")
        self.activate(Document([group]))
        group.detach()
        self.assertIsNotNone(source.parentNode())
        self.combo._update_selected_layer_name()
        self.assertIsNone(self.dock.settings.source_layer)
        self.assertIsNone(self.combo.currentData())
        self.assertEqual(app.values["source_layer_name"], "")

    def test_popup_saves_rename_before_rebuilding(self):
        source = Node("Source")
        self.activate(Document([source]))
        source.label = "Renamed"
        self.combo.showPopup()
        self.assertEqual(app.values["source_layer_name"], "Renamed")
        self.assertEqual(self.combo.currentText(), "Renamed")
        self.assertEqual(len(app.writes), 3)

    def test_popup_syncs_deletion_before_rebuilding(self):
        source = Node("Source")
        self.activate(Document([source]))
        source.detach()
        self.combo.showPopup()
        self.assertIsNone(self.dock.settings.source_layer)
        self.assertEqual(self.combo.count(), 1)
        self.assertEqual(app.values["source_layer_name"], "")

    def test_other_layer_changes_refresh_on_open_and_timer_pauses(self):
        source = Node("Source")
        doc = Document([source])
        self.activate(doc)
        doc.root.add_child(Node("New"))
        self.combo._update_selected_layer_name()
        self.assertEqual(self.combo.count(), 2)
        self.combo.showPopup()
        self.assertEqual(self.combo.count(), 3)
        self.assertFalse(self.combo._timer.isActive())
        self.combo.hidePopup()
        self.assertTrue(self.combo._timer.isActive())
        self.assertFalse(app.writes)

    def test_user_can_clear_source_with_placeholder(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.combo.setCurrentIndex(0)
        self.assertIsNone(self.dock.settings.source_layer)
        self.assertEqual(app.values["source_layer_name"], "")

    def test_document_switch_rebinds_name_and_preserves_other_settings(self):
        first, second = Node("Source"), Node("Source")
        self.activate(Document([first]))
        self.activate(Document([Node("Group", [second], "grouplayer")]))
        self.assertEqual(self.dock.settings.source_layer, second)
        self.assertEqual(self.combo.currentData(), second.id)
        self.assertEqual(self.combo.currentText(), "    Source")
        self.assertEqual(self.dock.settings.size, 25)
        self.assertFalse(app.writes)
        self.activate(None)
        self.assertFalse(self.combo.isEnabled())
        self.assertIsNone(self.dock.settings.source_layer)
        self.assertFalse(app.writes)

    def test_same_document_canvas_switch_does_not_rebuild(self):
        doc = Document([Node("Source")])
        self.activate(doc)
        with patch.object(self.combo, "update_value") as rebuild:
            self.activate(doc)
            rebuild.assert_not_called()

    def test_no_match_overwrites_persisted_name_on_next_save(self):
        self.activate(Document())
        self.assertIsNone(self.dock.settings.source_layer)
        self.dock.sample_size._widget.setValue(40)
        self.assertEqual(app.values["source_layer_name"], "")

    def test_enable_and_size_changes_save_without_losing_selection(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.dock.active.setChecked(True)
        self.dock.sample_size._widget.setValue(40)
        self.dock.active.setChecked(False)
        self.assertEqual(self.dock.settings.source_layer, source)
        self.assertEqual(app.values["active"], "False")
        self.assertEqual(app.values["size"], "40")
        self.assertEqual(app.values["source_layer_name"], "Source")

    def test_hidden_selector_does_not_poll(self):
        source = Node("Source")
        self.activate(Document([source]))
        self.dock.hide()
        source.label = "Renamed"
        self.combo._update_selected_layer_name()
        self.assertFalse(app.writes)


if __name__ == "__main__":
    unittest.main()
