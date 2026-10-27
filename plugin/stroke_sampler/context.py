from krita import Krita


def instance() -> Krita:
    instance = Krita.instance()

    if instance is None:
        raise RuntimeError("Krita instance not found")

    return instance


app: Krita = instance()
