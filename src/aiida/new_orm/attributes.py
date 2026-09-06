from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable

from typing_extensions import Self

from aiida.common import exceptions
from aiida.orm import fields as qb_fields

from .cli_adapter import CliAdapter
from .fields import (
    BaseField,
    BaseFieldConfig,
    BaseFieldDecorator,
    BaseFieldSpec,
    CliFieldInfo,
    EntityField,
    EntityFieldConfig,
    ModelFieldInfo,
    Storable,
)
from .model_adapter import ModelAdapter

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


_NodeT = t.TypeVar('_NodeT', bound=Storable)
_ValueT = t.TypeVar('_ValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)


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

        attributes = getattr(owner, 'attributes')
        attribute = getattr(attributes, self.spec.name)

        return t.cast(_QbFieldT, attribute)

    def __set__(self, instance: _NodeT, value: _ValueT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('attribute has not been assigned to a Node class')

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.fset is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no setter')

        if instance.is_stored:
            raise exceptions.ModificationNotAllowed(f'{self._owner.__name__}.{self._name} is immutable when stored')

        self.fset(instance, value)

    def setter(self, fset: Callable[[_NodeT, _ValueT], None], /) -> Self:
        """Set the setter and return this descriptor."""
        if self._config.readonly:
            raise TypeError('cannot define a setter for a read-only Node attribute')

        self.fset = fset
        self._spec = None

        return self


_ConfiguredQbFieldT = t.TypeVar('_ConfiguredQbFieldT', bound=qb_fields.QbField)


class ConfiguredAttributeDecorator(t.Protocol[_ConfiguredQbFieldT]):
    """Configured attribute decorator with a known QueryBuilder field type."""

    def __call__(
        self,
        fget: Callable[[_NodeT], _ValueT],
        /,
    ) -> NodeAttribute[_NodeT, _ValueT, _ConfiguredQbFieldT]: ...


_AdaptedEntityT = t.TypeVar('_AdaptedEntityT')
_AdaptedModelT = t.TypeVar('_AdaptedModelT')


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
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], int],
        /,
    ) -> NodeAttribute[_NodeT, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], int | None],
        /,
    ) -> NodeAttribute[_NodeT, int | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], float],
        /,
    ) -> NodeAttribute[_NodeT, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], float | None],
        /,
    ) -> NodeAttribute[_NodeT, float | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], datetime.datetime],
        /,
    ) -> NodeAttribute[_NodeT, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], datetime.datetime | None],
        /,
    ) -> NodeAttribute[_NodeT, datetime.datetime | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], str],
        /,
    ) -> NodeAttribute[_NodeT, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], str | None],
        /,
    ) -> NodeAttribute[_NodeT, str | None, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], list[_ValueT]],
        /,
    ) -> NodeAttribute[_NodeT, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], list[_ValueT] | None],
        /,
    ) -> NodeAttribute[_NodeT, list[_ValueT] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], tuple[_ValueT, ...]],
        /,
    ) -> NodeAttribute[_NodeT, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], tuple[_ValueT, ...] | None],
        /,
    ) -> NodeAttribute[_NodeT, tuple[_ValueT, ...] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_NodeT], dict[str, _ValueT]],
        /,
    ) -> NodeAttribute[_NodeT, dict[str, _ValueT], qb_fields.QbDictField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
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
    def __call__(  # type: ignore[overload-cannot-match]
        self,
        fget: Callable[[_NodeT], _ValueT],
        /,
    ) -> NodeAttribute[_NodeT, _ValueT, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        *,
        readonly: bool = False,
        required_once_stored: bool = False,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedEntityT, _AdaptedModelT, _QbFieldT],
        cli_field_info: CliFieldInfo | None = None,
        cli_adapter: CliAdapter[t.Any, t.Any] | None = None,
    ) -> ConfiguredAttributeDecorator[_QbFieldT]: ...

    @t.overload
    def __call__(
        self,
        *,
        readonly: bool = False,
        required_once_stored: bool = False,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: None = None,
        cli_field_info: CliFieldInfo | None = None,
        cli_adapter: CliAdapter[t.Any, t.Any] | None = None,
    ) -> Self: ...

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return self._call(*args, **kwargs)


attribute: NodeAttributeDecorator = NodeAttributeDecorator()


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


class NodeAttributesField(
    EntityField[
        _NodeT,
        dict[str, t.Any],
        qb_fields.QbAttributesField,
    ]
):
    """ORM entity field representing the typed Node attributes mapping."""

    def __init__(self, fget: Callable[[_NodeT], dict[str, t.Any]]) -> None:
        super().__init__(
            fget,
            config=EntityFieldConfig(
                may_be_large=True,
            ),
        )

        # The typed child registry depends on the concrete Node subclass.
        self._qb_fields: dict[type[_NodeT], qb_fields.QbAttributesField] = {}

    def _get_qb_field(self, owner: type[_NodeT]) -> qb_fields.QbAttributesField:
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
        fget: Callable[[_NodeT], dict[str, t.Any]],
        /,
    ) -> NodeAttributesField[_NodeT]:
        return NodeAttributesField(fget)


attributes_field = NodeAttributesFieldDecorator()
