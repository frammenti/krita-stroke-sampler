"""Layer filtering and document-local name lookup."""

import unittest

from krita_test_support import Document, Node, layer


class LayerTests(unittest.TestCase):
    def test_accepts_layers_and_excludes_masks(self):
        for kind in ("paintlayer", "grouplayer", "filelayer", "filterlayer",
                     "filllayer", "clonelayer", "vectorlayer"):
            self.assertTrue(layer.is_layer(Node("Layer", kind=kind)))
        for kind in ("transparencymask", "filtermask", "transformmask",
                     "selectionmask", "colorizemask"):
            self.assertFalse(layer.is_layer(Node("Mask", kind=kind)))

    def test_lookup_is_scoped_to_explicit_document(self):
        first, second = Node("Source"), Node("Source")
        self.assertEqual(layer.get_layer("Source", Document([first])), first)
        self.assertEqual(layer.get_layer("Source", Document([second])), second)
        self.assertIsNone(layer.get_layer("Source"))

    def test_lookup_handles_nested_and_duplicate_names(self):
        first, second = Node("Source"), Node("Source")
        doc = Document([Node("Group", [first], "grouplayer"), second])
        self.assertEqual(layer.get_layer("Source", doc), first)

    def test_lookup_rejects_mask_or_missing_name(self):
        doc = Document([Node("Mask", kind="transparencymask")])
        self.assertIsNone(layer.get_layer("Mask", doc))
        self.assertIsNone(layer.get_layer("Missing", doc))
