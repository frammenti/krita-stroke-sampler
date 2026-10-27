from typing import Optional

from krita import Document, Node


def is_layer(node: Node) -> bool:
    """
    A Krita Node can be either a layer or a mask.
    The sampler accepts layers only, not masks.

    Possible values are:
      - paintlayer,
      - grouplayer,
      - filelayer,
      - filterlayer,
      - filllayer,
      - clonelayer,
      - vectorlayer,
      - transparencymask,
      - filtermask,
      - transformmask,
      - selectionmask,
      - colorizemask.

    Reference: https://api.kde.org/legacy/krita/html/classNode.html#a58f4025f31c1bb44df0eb6df7b559e70
    """
    return node.type().endswith("layer")


def get_layer(name: str, document: Optional[Document] = None) -> Optional[Node]:
    """
    Resolve the layer name in the supplied document.
    Avoids depending on the global `app.activeDocument()` state.
    """

    if document is None:
        return None

    node = document.nodeByName(name)

    if node and not is_layer(node):
        return None

    return node
