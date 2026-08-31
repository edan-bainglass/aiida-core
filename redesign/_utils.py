import typing as t


def is_nullable(annotation: t.Any) -> bool:
    """Return whether an annotation accepts `None`."""
    return type(None) in t.get_args(annotation)


def make_nullable(annotation: t.Any) -> t.Any:
    """Return a nullable version of the annotation."""
    if is_nullable(annotation):
        return annotation

    return annotation | None


def make_required(annotation: t.Any) -> t.Any:
    """Return a required (non-nullable) version of the annotation."""
    if not is_nullable(annotation):
        return annotation

    return t.get_args(annotation)[0] if t.get_args(annotation) else annotation


def make_annotated(annotation: t.Any, metadata: list[t.Any]) -> t.Any:
    """Return an `Annotated` type compatible with Python 3.10."""
    if not metadata:
        return annotation

    return t.Annotated[(annotation, *metadata)]
