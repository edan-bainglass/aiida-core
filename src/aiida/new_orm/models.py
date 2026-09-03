from __future__ import annotations

import functools
import typing as t
from copy import deepcopy

import pydantic as pdt
from pydantic_core import PydanticUndefined
from typing_extensions import Self

from aiida.common.utils import (
    is_nullable,
    make_annotated,
    make_nullable,
    make_required,
)

from .fields import (
    EntityField,
    EntityFieldSpec,
    ModelFieldInfo,
    iter_fields,
)

__all__ = (
    'CreateModel',
    'EntityModel',
    'ModelsNamespace',
    'ReadModel',
    'UpdateModel',
)


_OwnerT = t.TypeVar('_OwnerT')


class EntityModel(pdt.BaseModel, t.Generic[_OwnerT]):
    """Base class for dynamically generated ORM entity models."""

    _minimal_model: t.ClassVar[type[EntityModel] | None] = None

    model_config = pdt.ConfigDict(
        extra='forbid',
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    # Set on each dynamically generated model class.
    _entity: t.ClassVar[type[_OwnerT]]
    _entity_fields: t.ClassVar[dict[str, EntityField]]
    _models_namespace: t.ClassVar[ModelsNamespace[t.Any]]

    @classmethod
    def field_spec(cls, name: str) -> EntityFieldSpec:
        """Return the canonical ORM entity specification for a model field."""
        return cls._entity_fields[name].spec

    @classmethod
    def from_entity(
        cls,
        entity: _OwnerT,
        *,
        context: dict[str, t.Any] | None = None,
        minimal: bool = False,
    ) -> Self:
        """Create a read model from an ORM entity."""
        values = cls._from_entity_field_values(entity, context=context, minimal=minimal)
        return cls.model_validate(values)

    @classmethod
    def _from_entity_field_values(
        cls,
        entity: _OwnerT,
        *,
        context: dict[str, t.Any] | None = None,
        minimal: bool = False,
    ) -> dict[str, t.Any]:
        """Convert ORM entity field values to model-side representations."""
        return {
            name: cls._models_namespace._to_model_value(
                field,
                getattr(entity, name),
                context=context,
            )
            for name, field in cls._entity_fields.items()
            if not (field.spec.may_be_large and minimal)
        }

    def _to_entity_field_values(self, *, only_set: bool = False) -> dict[str, t.Any]:
        """Convert model field values to entity representations."""
        names: t.Iterable[str] = self.model_fields_set if only_set else self.__class__.model_fields

        return {
            name: self.__class__._models_namespace._to_entity_value(
                self.__class__._entity_fields[name],
                getattr(self, name),
            )
            for name in names
        }

    @classmethod
    def minimize(cls) -> type[EntityModel]:
        """Return a derived model excluding fields marked as `may_be_large`."""
        if cls._minimal_model is not None:
            return cls._minimal_model

        model_fields: dict[str, t.Any] = {}

        for name, model_field in cls.model_fields.items():
            field = cls._entity_fields.get(name)

            if field is not None and field.spec.may_be_large:
                continue

            annotation = model_field.annotation
            field_info = deepcopy(model_field)

            if isinstance(annotation, type) and issubclass(annotation, EntityModel):
                annotation = annotation.minimize()
                field_info.annotation = annotation

                if any(field.is_required() for field in annotation.model_fields.values()):
                    field_info.default_factory = None

            model_fields[name] = (annotation, field_info)

        minimal_model = t.cast(
            type[EntityModel],
            pdt.create_model(
                f'Minimal{cls.__name__}',
                __config__=deepcopy(cls.model_config) | {'extra': 'ignore'},
                __base__=EntityModel,
                __module__=cls.__module__,
                __qualname__=f'{cls.__qualname__.rsplit(".", 1)[0]}.Minimal{cls.__name__}',
                **model_fields,
            ),
        )

        minimal_model._entity = cls._entity
        minimal_model._entity_fields = {
            name: field for name, field in cls._entity_fields.items() if name in model_fields
        }
        minimal_model._models_namespace = cls._models_namespace

        cls._minimal_model = minimal_model
        return minimal_model


class ReadModel(EntityModel[_OwnerT]):
    """Read projection of an ORM entity."""


class CreateModel(EntityModel[_OwnerT]):
    """Input projection for constructing an ORM entity."""

    def to_entity(self) -> _OwnerT:
        """Construct an ORM entity from this model."""
        return self.__class__._entity(**self._to_entity_field_values())


class UpdateModel(EntityModel[_OwnerT]):
    """PATCH-like projection for mutating an ORM entity."""

    def apply(self, entity: _OwnerT) -> _OwnerT:
        """Apply explicitly set values to an ORM entity."""
        for name, value in self._to_entity_field_values(only_set=True).items():
            setattr(entity, name, value)

        return entity


SupportedModel = t.Literal['read', 'create', 'update']


class ModelsNamespace(t.Generic[_OwnerT]):
    """Lazily generated model projections for one entity class."""

    def __init__(self, *, entity: type[_OwnerT] | None = None) -> None:
        self._entity = entity
        self._namespaces: dict[type[t.Any], Self] = {}

    @t.overload
    def __get__(self, instance: None, owner: type[_OwnerT]) -> Self: ...

    @t.overload
    def __get__(self, instance: object, owner: type[_OwnerT] | None = None) -> t.Never: ...

    def __get__(self, instance: object | None, owner: type[_OwnerT] | None = None) -> Self:
        if owner is None:
            raise AttributeError('models must be accessed through an entity class')

        if instance is not None:
            raise AttributeError(f"'models' must be accessed through the entity class; use {owner.__name__}.models")

        namespace = self._namespaces.get(owner)

        if namespace is None:
            namespace = type(self)(entity=owner)
            self._namespaces[owner] = namespace

        return namespace

    @functools.cached_property
    def read(self) -> type[ReadModel[_OwnerT]]:
        """Return the read projection for the entity."""
        return self._build_model('read')

    @functools.cached_property
    def create(self) -> type[CreateModel[_OwnerT]]:
        """Return the create projection for the entity."""
        return self._build_model('create')

    @functools.cached_property
    def update(self) -> type[UpdateModel[_OwnerT]]:
        """Return the update projection for the entity."""
        return self._build_model('update')

    def _model_field_annotation(self, field: EntityField, projection: SupportedModel) -> t.Any:
        """Return the model-side annotation for an entity field."""
        spec = field.spec

        if field.model_adapter is None:
            annotation = spec.value_type
        else:
            annotation = field.model_adapter.model_type

        if is_nullable(spec.value_type):
            annotation = make_nullable(annotation)

        if projection == 'read' and spec.required_once_stored:
            annotation = make_required(annotation)

        return annotation

    def _to_model_value(
        self,
        field: EntityField,
        value: t.Any,
        *,
        context: t.Any | None = None,
    ) -> t.Any:
        """Convert an entity field value to its model representation."""
        if value is not None and (adapter := field.model_adapter):
            return adapter.to_model(value, context=context)

        return value

    def _to_entity_value(self, field: EntityField, value: t.Any) -> t.Any:
        """Convert a model field value to its entity representation."""
        if value is not None and (adapter := field.model_adapter):
            return adapter.to_entity(value)

        return value

    @t.overload
    def _build_model(self, projection: t.Literal['read']) -> type[ReadModel[_OwnerT]]: ...

    @t.overload
    def _build_model(self, projection: t.Literal['create']) -> type[CreateModel[_OwnerT]]: ...

    @t.overload
    def _build_model(self, projection: t.Literal['update']) -> type[UpdateModel[_OwnerT]]: ...

    def _build_model(self, projection: SupportedModel) -> type[EntityModel[_OwnerT]]:
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to an entity class')

        model_fields: dict[str, t.Any] = {}
        entity_fields: dict[str, EntityField] = {}

        for name, field in iter_fields(self._entity).items():
            spec = field.spec

            if not _include_field(spec, projection):
                continue

            model_fields[name] = _build_model_field(
                self._model_field_annotation(field, projection),
                description=spec.description,
                model_field_info=field.model_field_info,
                readonly=spec.readonly,
            )
            entity_fields[name] = field

        model_base = _model_base(projection)
        class_name = f'{projection.capitalize()}Model'

        model = t.cast(
            type[EntityModel[_OwnerT]],
            pdt.create_model(
                f'{self._entity.__name__}{class_name}',
                __base__=model_base,
                __module__=self._entity.__module__,
                __qualname__=f'{self._entity.__qualname__}.{class_name}',
                **model_fields,
            ),
        )

        model._entity = self._entity
        model._entity_fields = entity_fields
        model._models_namespace = self

        return model


def _model_base(projection: SupportedModel) -> type[EntityModel]:
    """Return the base class for a model projection."""
    if projection == 'read':
        return ReadModel

    if projection == 'create':
        return CreateModel

    if projection == 'update':
        return UpdateModel

    t.assert_never(projection)


def _include_field(spec: EntityFieldSpec, projection: SupportedModel) -> bool:
    """Return whether a field belongs to a model projection."""
    if projection == 'read':
        return True

    if projection == 'create':
        return not spec.readonly

    if projection == 'update':
        return spec.updatable

    t.assert_never(projection)


def _build_model_field(
    model_type: t.Any,
    *,
    description: str = '',
    model_field_info: ModelFieldInfo | None = None,
    readonly: bool = False,
) -> tuple[t.Any, t.Any]:
    """Build the Pydantic declaration for a model field."""
    field_info = model_field_info if model_field_info is not None else ModelFieldInfo()
    field_dict = field_info.asdict()

    metadata = field_dict['metadata']
    attributes = dict(field_dict['attributes'])

    if field_info.default is not PydanticUndefined:
        attributes['default'] = field_info.default
    elif is_nullable(model_type):
        attributes['default'] = None

    if attributes['description'] is None and description:
        attributes['description'] = description

    if readonly:
        json_schema_extra = attributes['json_schema_extra']

        if json_schema_extra is None:
            json_schema_extra = {'readOnly': True}

        elif isinstance(json_schema_extra, dict):
            json_schema_extra = dict(json_schema_extra)
            json_schema_extra.setdefault('readOnly', True)

        else:
            original_json_schema_extra = json_schema_extra

            def json_schema_extra(schema: dict[str, t.Any], *args: t.Any) -> None:
                original_json_schema_extra(schema, *args)
                schema.setdefault('readOnly', True)

        attributes['json_schema_extra'] = json_schema_extra

    annotation = make_annotated(model_type, metadata)

    return annotation, ModelFieldInfo(**attributes)
