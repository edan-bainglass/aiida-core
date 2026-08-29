from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable

from fields import (
    BaseField,
    BaseFieldConfig,
    BaseFieldDecorator,
    BaseFieldSpec,
    EntityField,
    ModelFieldInfo,
    _QbFieldT,
    _ValueT,
)
from typing_extensions import Self

from aiida.orm import fields as qb_fields

if t.TYPE_CHECKING:
    from models import ModelAdapter
    from node import Node


__all__ = (
    'NodeAttribute',
    'NodeAttributeSpec',
    'NodeAttributesField',
    'attribute',
    'attributes_field',
    'iter_attributes',
)


@dataclasses.dataclass(frozen=True)
class NodeAttributeSpec(BaseFieldSpec):
    """Canonical semantic description of a typed Node attribute."""


@dataclasses.dataclass(frozen=True)
class NodeAttributeConfig(BaseFieldConfig):
    """Unresolved configuration supplied to the `attribute` decorator."""


_NodeT = t.TypeVar('_NodeT', bound='Node')


class NodeAttribute(
    BaseField[
        _NodeT,
        _ValueT,
        _QbFieldT,
        NodeAttributeSpec,
        NodeAttributeConfig,
    ],
):
    """Descriptor declaring a typed key in the Node attributes mapping."""

    config_type = NodeAttributeConfig
    spec_type = NodeAttributeSpec

    @t.overload
    def __get__(self, instance: None, owner: type[_NodeT]) -> _QbFieldT: ...

    @t.overload
    def __get__(self, instance: _NodeT, owner: type[_NodeT] | None = None) -> _ValueT: ...

    def __get__(self, instance: _NodeT | None, owner: type[_NodeT] | None = None) -> _ValueT | _QbFieldT:
        if instance is not None:
            return self.fget(instance)

        if owner is None:
            raise AttributeError('Node attribute must be accessed through a Node class')

        return t.cast(_QbFieldT, getattr(owner.attributes, self.spec.name))


class NodeAttributeDecorator(
    BaseFieldDecorator[
        _NodeT,
        _ValueT,
        NodeAttributeConfig,
        NodeAttribute[t.Any, t.Any, qb_fields.QbField],
    ],
):
    """Decorator for typed Node attributes."""

    config_type = NodeAttributeConfig
    field_type = NodeAttribute

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], int],
        /,
    ) -> NodeAttribute[_NodeT, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], int | None],
        /,
    ) -> NodeAttribute[_NodeT, int | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], float],
        /,
    ) -> NodeAttribute[_NodeT, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], float | None],
        /,
    ) -> NodeAttribute[_NodeT, float | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], datetime.datetime],
        /,
    ) -> NodeAttribute[_NodeT, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], datetime.datetime | None],
        /,
    ) -> NodeAttribute[_NodeT, datetime.datetime | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], str],
        /,
    ) -> NodeAttribute[_NodeT, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], str | None],
        /,
    ) -> NodeAttribute[_NodeT, str | None, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], list[_ValueT]],
        /,
    ) -> NodeAttribute[_NodeT, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], list[_ValueT] | None],
        /,
    ) -> NodeAttribute[_NodeT, list[_ValueT] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], tuple[_ValueT, ...]],
        /,
    ) -> NodeAttribute[_NodeT, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], tuple[_ValueT, ...] | None],
        /,
    ) -> NodeAttribute[_NodeT, tuple[_ValueT, ...] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], dict[str, _ValueT]],
        /,
    ) -> NodeAttribute[_NodeT, dict[str, _ValueT], qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], dict[str, _ValueT] | None],
        /,
    ) -> NodeAttribute[_NodeT, dict[str, _ValueT] | None, qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], object],
        /,
    ) -> NodeAttribute[_NodeT, object, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], _ValueT],
        /,
    ) -> NodeAttribute[_NodeT, _ValueT, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[t.Any, t.Any] | None = None,
    ) -> Self: ...

    def __call__(
        self,
        fget: Callable[[_NodeT], _ValueT] | None = None,
        /,
        **kwargs: t.Any,
    ) -> t.Any:
        return super().__call__(fget, **kwargs)


attribute = NodeAttributeDecorator()


def iter_attributes(entity: type) -> dict[str, NodeAttribute]:
    """Return all effective typed attributes on a Node hierarchy."""
    result: dict[str, NodeAttribute] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, NodeAttribute):
                result[name] = value
            elif name in result:
                del result[name]

    return result


class NodeAttributesField(EntityField[_NodeT, dict[str, t.Any], qb_fields.QbAttributesField]):
    """ORM entity field representing the typed Node attributes mapping."""

    def __init__(self, fget: Callable[[_NodeT], dict[str, t.Any]]) -> None:
        super().__init__(fget)

        # The typed child registry depends on the concrete Node subclass.
        self._qb_fields: dict[type[_NodeT], qb_fields.QbAttributesField] = {}

    def _get_qb_field(self, owner: type[_NodeT]) -> qb_fields.QbAttributesField:
        """Return the attributes field specialized for the concrete Node type."""
        if qb_field := self._qb_fields.get(owner):
            return qb_field

        spec = self.spec
        qb_field = t.cast(
            qb_fields.QbAttributesField,
            qb_fields.add_field(
                spec.backend_key,
                dtype=spec.value_type,
                doc=spec.description,
                is_attribute=False,
            ),
        )

        qb_field._typed_children = {
            name: qb_fields.add_field(
                name,
                dtype=node_attribute.spec.value_type,
                doc=node_attribute.spec.description,
                is_attribute=True,
            )
            for name, node_attribute in iter_attributes(owner).items()
        }

        self._qb_fields[owner] = qb_field
        return qb_field


class NodeAttributesFieldDecorator:
    """Decorator for the top-level Node `attributes` field."""

    def __call__(
        self,
        fget: Callable[[_NodeT], dict[str, t.Any]],
        /,
    ) -> NodeAttributesField[_NodeT]:
        return NodeAttributesField(fget)


attributes_field = NodeAttributesFieldDecorator()
