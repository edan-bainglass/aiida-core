from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable

from _types import NodeType
from fields import (
    BaseField,
    BaseFieldConfig,
    BaseFieldDecorator,
    BaseFieldSpec,
    EntityField,
    ModelFieldInfo,
    _AdaptedOrmT,
    _QbFieldT,
    _ValueT,
)
from model_adapter import ModelAdapter
from typing_extensions import Self

from aiida.common import exceptions
from aiida.orm import fields as qb_fields

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


class NodeAttribute(
    BaseField[
        NodeType,
        _ValueT,
        _QbFieldT,
        NodeAttributeSpec,
        NodeAttributeConfig,
    ],
):
    """Descriptor declaring a typed key in the Node attributes mapping."""

    config_type = NodeAttributeConfig
    spec_type = NodeAttributeSpec

    def __init__(
        self,
        fget: Callable[[NodeType], _ValueT],
        fset: Callable[[NodeType, _ValueT], None] | None = None,
        *,
        config: NodeAttributeConfig | None = None,
    ) -> None:
        super().__init__(fget, config=config)
        self.fset = fset

    @t.overload
    def __get__(self, instance: None, owner: type[NodeType]) -> _QbFieldT: ...

    @t.overload
    def __get__(self, instance: NodeType, owner: type[NodeType] | None = None) -> _ValueT: ...

    def __get__(self, instance: NodeType | None, owner: type[NodeType] | None = None) -> _ValueT | _QbFieldT:
        if instance is not None:
            return self.fget(instance)

        if owner is None:
            raise AttributeError('Node attribute must be accessed through a Node class')

        return t.cast(_QbFieldT, getattr(owner.attributes, self.spec.name))

    def __set__(self, instance: NodeType, value: _ValueT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('attribute has not been assigned to a Node class')

        if self.fset is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no setter')

        if instance.is_stored:
            raise exceptions.ModificationNotAllowed(f'{self._owner.__name__}.{self._name} is immutable when stored')

        self.fset(instance, value)

    def setter(self, fset: Callable[[NodeType, _ValueT], None], /) -> Self:
        """Set the setter and return this descriptor."""
        self.fset = fset
        self._spec = None
        return self


class ConfiguredAttributeDecorator(t.Protocol[_QbFieldT]):
    """Configured attribute decorator with a known QueryBuilder field type."""

    def __call__(
        self,
        fget: Callable[[NodeType], _ValueT],
        /,
    ) -> NodeAttribute[NodeType, _ValueT, _QbFieldT]: ...


class NodeAttributeDecorator(
    BaseFieldDecorator[
        NodeType,
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
        fget: Callable[[NodeType], int],
        /,
    ) -> NodeAttribute[NodeType, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], int | None],
        /,
    ) -> NodeAttribute[NodeType, int | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], float],
        /,
    ) -> NodeAttribute[NodeType, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], float | None],
        /,
    ) -> NodeAttribute[NodeType, float | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], datetime.datetime],
        /,
    ) -> NodeAttribute[NodeType, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], datetime.datetime | None],
        /,
    ) -> NodeAttribute[NodeType, datetime.datetime | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], str],
        /,
    ) -> NodeAttribute[NodeType, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], str | None],
        /,
    ) -> NodeAttribute[NodeType, str | None, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], list[_ValueT]],
        /,
    ) -> NodeAttribute[NodeType, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], list[_ValueT] | None],
        /,
    ) -> NodeAttribute[NodeType, list[_ValueT] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], tuple[_ValueT, ...]],
        /,
    ) -> NodeAttribute[NodeType, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], tuple[_ValueT, ...] | None],
        /,
    ) -> NodeAttribute[NodeType, tuple[_ValueT, ...] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], dict[str, _ValueT]],
        /,
    ) -> NodeAttribute[NodeType, dict[str, _ValueT], qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], dict[str, _ValueT] | None],
        /,
    ) -> NodeAttribute[NodeType, dict[str, _ValueT] | None, qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], object],
        /,
    ) -> NodeAttribute[NodeType, object, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[NodeType], _ValueT],
        /,
    ) -> NodeAttribute[NodeType, _ValueT, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedOrmT, int],
    ) -> ConfiguredAttributeDecorator[qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedOrmT, float],
    ) -> ConfiguredAttributeDecorator[qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedOrmT, str],
    ) -> ConfiguredAttributeDecorator[qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedOrmT, list[_ValueT]],
    ) -> ConfiguredAttributeDecorator[qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedOrmT, tuple[_ValueT, ...]],
    ) -> ConfiguredAttributeDecorator[qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedOrmT, dict[str, _ValueT]],
    ) -> ConfiguredAttributeDecorator[qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        *,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[t.Any, t.Any] | None = None,
    ) -> Self: ...

    def __call__(
        self,
        fget: Callable[[NodeType], _ValueT] | None = None,
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


class NodeAttributesField(EntityField[NodeType, dict[str, t.Any], qb_fields.QbAttributesField]):
    """ORM entity field representing the typed Node attributes mapping."""

    def __init__(self, fget: Callable[[NodeType], dict[str, t.Any]]) -> None:
        super().__init__(fget)

        # The typed child registry depends on the concrete Node subclass.
        self._qb_fields: dict[type[NodeType], qb_fields.QbAttributesField] = {}

    def _build_qb_field(self) -> qb_fields.QbAttributesField:
        """Build the QueryBuilder attributes field."""
        return t.cast(qb_fields.QbAttributesField, super()._build_qb_field())

    def _get_qb_field(self, owner: type[NodeType]) -> qb_fields.QbAttributesField:
        """Return the attributes field specialized for the concrete Node type."""
        if qb_field := self._qb_fields.get(owner):
            return qb_field

        qb_field = self._build_qb_field()

        qb_field._typed_children = {
            name: qb_fields.add_field(
                name,
                dtype=node_attribute.adapted_type,
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
        fget: Callable[[NodeType], dict[str, t.Any]],
        /,
    ) -> NodeAttributesField[NodeType]:
        return NodeAttributesField(fget)


attributes_field = NodeAttributesFieldDecorator()
