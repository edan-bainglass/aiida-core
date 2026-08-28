from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable

from fields import BaseFieldSpec, ModelFieldInfo, OrmField

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


_NodeT = t.TypeVar('_NodeT', bound='Node')
_ValueT = t.TypeVar('_ValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)


@dataclasses.dataclass(frozen=True)
class NodeAttributeSpec(BaseFieldSpec):
    """Canonical semantic description of a typed Node attribute."""


@dataclasses.dataclass(frozen=True)
class _AttributeConfig:
    """Unresolved configuration supplied to the `attribute` decorator."""

    model_field_info: ModelFieldInfo | None = None
    model_adapter: ModelAdapter[t.Any, t.Any] | None = None


class NodeAttribute(t.Generic[_NodeT, _ValueT, _QbFieldT]):
    """Descriptor declaring a typed key in the Node attributes mapping."""

    def __init__(
        self,
        fget: Callable[[_NodeT], _ValueT],
        *,
        config: _AttributeConfig | None = None,
    ) -> None:
        self.fget = fget
        self.__doc__ = getattr(fget, '__doc__', None)

        self._name: str | None = None
        self._config = config or _AttributeConfig()
        self._spec: NodeAttributeSpec | None = None

    def __set_name__(self, owner: type[_NodeT], name: str) -> None:
        self._name = name

    @property
    def spec(self) -> NodeAttributeSpec:
        """Return the lazily resolved attribute specification."""
        if self._spec is None:
            self._spec = self._build_spec()

        return self._spec

    @property
    def model_field_info(self) -> ModelFieldInfo | None:
        """Return optional Pydantic-specific field configuration."""
        return self._config.model_field_info

    @property
    def model_adapter(self) -> ModelAdapter[t.Any, t.Any] | None:
        """Return the ORM/model value adapter."""
        return self._config.model_adapter

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

    def _build_spec(self) -> NodeAttributeSpec:
        """Resolve the declaration into the canonical attribute specification."""
        if self._name is None:
            raise RuntimeError('attribute has not been assigned to a Node class')

        value_type = t.get_type_hints(self.fget).get('return', t.Any)

        return NodeAttributeSpec(
            name=self._name,
            value_type=value_type,
            description=(self.__doc__ or '').strip(),
        )


class NodeAttributeDecorator:
    """Decorator factory for typed Node attributes."""

    def __init__(self, config: _AttributeConfig | None = None) -> None:
        self._config = config or _AttributeConfig()

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], int],
        /,
    ) -> NodeAttribute[_NodeT, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], float],
        /,
    ) -> NodeAttribute[_NodeT, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], datetime.datetime],
        /,
    ) -> NodeAttribute[_NodeT, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], str],
        /,
    ) -> NodeAttribute[_NodeT, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], list[_ValueT]],
        /,
    ) -> NodeAttribute[_NodeT, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], tuple[_ValueT, ...]],
        /,
    ) -> NodeAttribute[_NodeT, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_NodeT], dict[str, _ValueT]],
        /,
    ) -> NodeAttribute[_NodeT, dict[str, _ValueT], qb_fields.QbDictField]: ...

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
    ) -> t.Self: ...

    def __call__(
        self,
        fget: Callable[[_NodeT], _ValueT] | None = None,
        /,
        **kwargs: t.Any,
    ) -> t.Any:
        if fget is None:
            return type(self)(_AttributeConfig(**kwargs))

        return NodeAttribute(fget, config=self._config)


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


class NodeAttributesField(OrmField[_NodeT, dict[str, t.Any], qb_fields.QbAttributesField]):
    """ORM field representing the typed Node attributes mapping."""

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
