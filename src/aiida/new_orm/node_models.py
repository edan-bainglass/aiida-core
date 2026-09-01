from __future__ import annotations

import functools
import typing as t

import pydantic as pdt
from typing_extensions import Self

from .attributes import NodeAttributesField, iter_attributes
from .fields import EntityField
from .models import ModelsNamespace, SupportedModel, _build_model_field

__all__ = ('NodeModelsNamespace',)

_OwnerT = t.TypeVar('_OwnerT')


class NodeModelsNamespace(ModelsNamespace[_OwnerT]):
    """Model namespace with Node-specific attribute handling."""

    @t.overload
    def __get__(self, instance: None, owner: type[_OwnerT]) -> Self: ...

    @t.overload
    def __get__(self, instance: object, owner: type[_OwnerT] | None = None) -> t.Never: ...

    def __get__(self, instance: object | None, owner: type[_OwnerT] | None = None) -> Self:
        return super().__get__(instance, owner)

    @functools.cached_property
    def attributes(self) -> type[pdt.BaseModel]:
        """Return the lazily generated nested attributes model."""
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to a Node class')

        return _build_attributes_model(self._entity)

    def _model_field_annotation(self, orm_field: EntityField, projection: SupportedModel) -> t.Any:
        """Return the model-side annotation for a Node field."""
        if isinstance(orm_field, NodeAttributesField):
            return self.attributes

        return super()._model_field_annotation(orm_field, projection)

    def _to_model_value(self, orm_field: EntityField, value: t.Any) -> t.Any:
        """Convert a Node field value to its model-side representation."""
        if isinstance(orm_field, NodeAttributesField):
            if self._entity is None:
                raise RuntimeError('model namespace is not bound to a Node class')

            return _attributes_to_model(self._entity, value)

        return super()._to_model_value(orm_field, value)

    def _to_orm_value(self, orm_field: EntityField, value: t.Any) -> t.Any:
        """Convert a model field value to its Node-side representation."""
        if isinstance(orm_field, NodeAttributesField):
            if self._entity is None:
                raise RuntimeError('model namespace is not bound to a Node class')

            return _attributes_to_orm(self._entity, value)

        return super()._to_orm_value(orm_field, value)


def _build_attributes_model(node_type: type[_OwnerT]) -> type[pdt.BaseModel]:
    """Build the nested attributes model for a Node type."""
    model_fields: dict[str, t.Any] = {}

    for name, node_attribute in iter_attributes(node_type).items():
        spec = node_attribute.spec
        model_type = (
            node_attribute.model_adapter.model_type if node_attribute.model_adapter is not None else spec.value_type
        )

        model_fields[name] = _build_model_field(
            model_type,
            description=spec.description,
            model_field_info=node_attribute.model_field_info,
        )

    extra_attributes = node_type.__dict__.get('_extra_attributes', 'forbid')

    return pdt.create_model(
        f'{node_type.__name__}AttributesModel',
        __config__=pdt.ConfigDict(
            extra=extra_attributes,
            serialize_by_alias=True,
            validate_by_alias=True,
            validate_by_name=True,
        ),
        __module__=node_type.__module__,
        __qualname__=f'{node_type.__qualname__}.AttributesModel',
        **model_fields,
    )


def _attributes_to_model(node_type: type[_OwnerT], value: dict[str, t.Any]) -> dict[str, t.Any]:
    """Convert raw Node attributes to their model-side representations."""
    values = dict(value)

    for name, node_attribute in iter_attributes(node_type).items():
        if name not in values:
            continue

        if values[name] is not None and (adapter := node_attribute.model_adapter):
            values[name] = adapter.to_model(values[name])

    return values


def _attributes_to_orm(node_type: type[_OwnerT], value: pdt.BaseModel | dict[str, t.Any]) -> dict[str, t.Any]:
    """Convert a nested attributes model to raw ORM attributes."""
    values = value.model_dump() if isinstance(value, pdt.BaseModel) else dict(value)

    for name, node_attribute in iter_attributes(node_type).items():
        if name not in values:
            continue

        if values[name] is not None and (adapter := node_attribute.model_adapter):
            values[name] = adapter.to_orm(values[name])

    return values
