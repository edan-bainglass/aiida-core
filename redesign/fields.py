from __future__ import annotations

import typing as t


class FieldSpec:
    def __init__(  # noqa: PLR0917
        self,
        backend_key: str,
        value_type: type | None = None,
        default: t.Any | None = None,
        description: str | None = None,
        readonly: bool = False,
        example: t.Any | None = None,
    ):
        self.backend_key = backend_key
        self.value_type = value_type
        self.default = default
        self.readonly = readonly
        self.description = description
        self.example = example


def field(**kwargs):
    def decorator(func):
        func._field_spec = FieldSpec(
            backend_key=kwargs.get('backend_key', func.__name__),
            value_type=kwargs.get('value_type', func.__annotations__.get('return', None)),
            default=kwargs.get('default', None),
            description=kwargs.get('description', func.__doc__),
            readonly=kwargs.get('readonly', False),
            example=kwargs.get('example', None),
        )
        return func

    return decorator
