from krita import Krita


def instance() -> Krita:
    _app = Krita.instance()

    if _app is None:
        raise RuntimeError("Krita instance not found")

    return _app


app: Krita = instance()
