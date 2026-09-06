from __future__ import annotations

import functools
import typing as t

import pydantic as pdt

from aiida.common.utils import (
    is_nullable,
    make_nullable,
    make_required,
)

from .attributes import (
    NodeAttribute,
    NodeAttributesColumn,
    iter_attributes,
)
from .columns import Column
from .models import (
    EntityModel,
    ModelsNamespace,
    OrmModel,
    SupportedModel,
    _build_model_field,
)

if t.TYPE_CHECKING:
    from .node import Node

__all__ = ('NodeModelsNamespace',)


_NodeT = t.TypeVar('_NodeT', bound='Node')
_AttributesProjection = t.Literal['read', 'create']


class NodeModelsNamespace(ModelsNamespace[_NodeT]):
    """Model namespace for Nodes with typed nested attributes."""

    @functools.cached_property
    def attributes(self) -> type[OrmModel[_NodeT]]:
        """Return the canonical persisted/read attributes model."""
        return self._build_attributes_model('read')

    @functools.cached_property
    def _create_attributes(self) -> type[OrmModel[_NodeT]]:
        """Return the attributes model used by the Node create projection."""
        return self._build_attributes_model('create')

    def _model_field_annotation(self, column: Column, projection: SupportedModel) -> t.Any:
        """Return the model-side annotation for a Node column."""
        if isinstance(column, NodeAttributesColumn):
            if projection == 'update':
                raise RuntimeError('attributes are immutable and cannot have an update projection')

            return self._attributes_model_annotation(projection)

        return super()._model_field_annotation(column, projection)

    def _attributes_model_annotation(self, projection: _AttributesProjection) -> type[OrmModel[_NodeT]]:
        """Return the attributes model for a Node projection."""
        if projection == 'read':
            return self.attributes

        return self._create_attributes

    def _to_model_value(
        self,
        column: Column,
        value: t.Any,
        *,
        context: t.Any | None = None,
    ) -> t.Any:
        """Convert a Node column value to its model representation."""
        if isinstance(column, NodeAttributesColumn):
            return self._attributes_to_model_value(value, context=context)

        return super()._to_model_value(column, value, context=context)

    def _to_entity_value(self, column: Column, value: t.Any) -> t.Any:
        """Convert a model value to its Node entity representation."""
        if isinstance(column, NodeAttributesColumn):
            return self._model_to_attributes_value(value)

        return super()._to_entity_value(column, value)

    def _build_attributes_model(self, projection: _AttributesProjection) -> type[OrmModel[_NodeT]]:
        """Build the typed attributes model for a Node projection."""
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to a Node class')

        model_fields: dict[str, t.Any] = {}

        for name, attribute in iter_attributes(self._entity).items():
            spec = attribute.spec

            if projection == 'create' and spec.readonly:
                continue

            annotation = self._attribute_model_annotation(attribute, projection)

            model_fields[name] = _build_model_field(
                annotation,
                description=spec.description,
                model_field_info=attribute.model_field_info,
                readonly=spec.readonly,
            )

        class_name = 'AttributesModel' if projection == 'read' else 'CreateAttributesModel'
        extra = self._entity.__dict__.get('_extra_attributes', 'forbid')

        model = t.cast(
            type[OrmModel[_NodeT]],
            pdt.create_model(
                f'{self._entity.__name__}{class_name}',
                __base__=OrmModel,
                __config__={
                    **EntityModel.model_config,
                    'extra': extra,
                },
                __module__=self._entity.__module__,
                __qualname__=f'{self._entity.__qualname__}.{class_name}',
                **model_fields,
            ),
        )

        return model

    def _attribute_model_annotation(
        self,
        attribute: NodeAttribute,
        projection: _AttributesProjection,
    ) -> t.Any:
        """Return the model-side annotation for a typed Node attribute."""
        spec = attribute.spec

        annotation = attribute.model_adapter.model_type if attribute.model_adapter is not None else spec.value_type

        if is_nullable(spec.value_type):
            annotation = make_nullable(annotation)

        if projection == 'read' and spec.required_once_stored:
            annotation = make_required(annotation)

        return annotation

    def _attributes_to_model_value(
        self,
        attributes: dict[str, t.Any],
        *,
        context: dict[str, t.Any] | None = None,
    ) -> dict[str, t.Any]:
        """Convert Node attributes to model-side representations."""
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to a Node class')

        values = dict(attributes)

        for name, attribute in iter_attributes(self._entity).items():
            if name not in values:
                continue

            if values[name] is not None and (adapter := attribute.model_adapter):
                values[name] = adapter.to_model(values[name], context=context)

        return values

    def _model_to_attributes_value(self, model: OrmModel[_NodeT] | dict[str, t.Any]) -> dict[str, t.Any]:
        """Convert model-side Node attributes to ORM representations."""
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to a Node class')

        values = model.model_dump() if isinstance(model, pdt.BaseModel) else dict(model)
        print(values)

        for name, node_attribute in iter_attributes(self._entity).items():
            if name not in values:
                continue

            if values[name] is not None and (adapter := node_attribute.model_adapter):
                values[name] = adapter.to_entity(values[name])

        return values
