from __future__ import annotations

import abc
import functools
import typing as t

import pydantic as pdt
from _types import EntityType
from fields import (
    EntityField,
    EntityFieldSpec,
    ModelField,
    ModelFieldInfo,
    iter_fields,
)
from pydantic_core import PydanticUndefined
from typing_extensions import Self

from aiida.common.lang import classproperty

__all__ = (
    'CreateModel',
    'ModelAdapter',
    'ModelsNamespace',
    'OrmModel',
    'ReadModel',
    'UpdateModel',
)


_ModelName = t.Literal['read', 'create', 'update']

_OrmValueT = t.TypeVar('_OrmValueT')
_ModelValueT = t.TypeVar('_ModelValueT')


class ModelAdapter(abc.ABC, t.Generic[_OrmValueT, _ModelValueT]):
    """Adapt between ORM and model representations of a value."""

    _model_type: t.ClassVar[t.Any] = None

    @classproperty
    def model_type(cls) -> t.Any:  # noqa: N805
        if cls._model_type is None:
            try:
                cls._model_type = t.get_type_hints(cls.to_model)['return']
            except KeyError:
                raise TypeError(f'`{cls.__name__}.to_model` must have a return annotation') from None

        return cls._model_type

    @abc.abstractmethod
    def to_model(self, value: _OrmValueT) -> _ModelValueT:
        """Convert an ORM value to its model representation."""

    @abc.abstractmethod
    def to_orm(self, value: _ModelValueT) -> _OrmValueT:
        """Convert a model value to its ORM representation."""


class OrmModel(pdt.BaseModel, t.Generic[EntityType]):
    """Base class for dynamically generated ORM models."""

    model_config = pdt.ConfigDict(
        extra='forbid',
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    # Shadow Pydantic's deprecated implementation.
    from_orm: t.ClassVar[None] = None

    # Set on each dynamically generated model class.
    _entity: t.ClassVar[type[EntityType]]
    _orm_fields: t.ClassVar[dict[str, EntityField]]
    _models_namespace: t.ClassVar[ModelsNamespace[t.Any]]

    @classmethod
    def field_spec(cls, name: str) -> EntityFieldSpec:
        """Return the canonical ORM specification for a model field."""
        return cls._orm_fields[name].spec

    @classmethod
    def _from_orm_field_values(cls, entity: EntityType) -> dict[str, t.Any]:
        """Convert ORM entity field values to model-side representations."""
        return {
            name: cls._models_namespace._to_model_value(orm_field, getattr(entity, name))
            for name, orm_field in cls._orm_fields.items()
        }

    def _to_orm_field_values(self, *, only_set: bool = False) -> dict[str, t.Any]:
        """Convert model field values to ORM-side representations."""
        names: t.Iterable[str] = self.model_fields_set if only_set else self.__class__.model_fields

        return {
            name: self.__class__._models_namespace._to_orm_value(
                self.__class__._orm_fields[name],
                getattr(self, name),
            )
            for name in names
        }


class ReadModel(OrmModel[EntityType]):
    """Read projection of an ORM entity."""

    @classmethod
    def from_orm(cls, entity: EntityType) -> Self:
        """Create a read model from an ORM entity."""
        return cls.model_validate(cls._from_orm_field_values(entity))


class CreateModel(OrmModel[EntityType]):
    """Input projection for constructing an ORM entity."""

    def to_orm(self) -> EntityType:
        """Construct an ORM entity from this model."""
        return t.cast(EntityType, self.__class__._entity(**self._to_orm_field_values()))


class UpdateModel(OrmModel[EntityType]):
    """PATCH-like projection for mutating an ORM entity."""

    def apply(self, entity: EntityType) -> EntityType:
        """Apply explicitly set values to an ORM entity."""
        for name, value in self._to_orm_field_values(only_set=True).items():
            setattr(entity, name, value)

        return entity


class ModelsNamespace(t.Generic[EntityType]):
    """Lazily generated model projections for one entity class."""

    def __init__(self, *, entity: type[EntityType] | None = None) -> None:
        self._entity = entity
        self._namespaces: dict[type[t.Any], Self] = {}

    @t.overload
    def __get__(self, instance: None, owner: type[EntityType]) -> Self: ...

    @t.overload
    def __get__(self, instance: object, owner: type[EntityType] | None = None) -> t.Never: ...

    def __get__(self, instance: object | None, owner: type[EntityType] | None = None) -> Self:
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
    def read(self) -> type[ReadModel[EntityType]]:
        """Return the read projection for the entity."""
        return self._build_model('read')

    @functools.cached_property
    def create(self) -> type[CreateModel[EntityType]]:
        """Return the create projection for the entity."""
        return self._build_model('create')

    @functools.cached_property
    def update(self) -> type[UpdateModel[EntityType]]:
        """Return the update projection for the entity."""
        return self._build_model('update')

    def _model_field_type(self, orm_field: EntityField) -> t.Any:
        """Return the model-side annotation for an ORM field."""
        spec = orm_field.spec

        if orm_field.model_adapter is None:
            return spec.value_type

        model_type = orm_field.model_adapter.model_type

        if _is_nullable(spec.value_type):
            model_type = _make_nullable(model_type)

        return model_type

    def _to_model_value(self, orm_field: EntityField, value: t.Any) -> t.Any:
        """Convert an ORM field value to its model-side representation."""
        if value is not None and (adapter := orm_field.model_adapter):
            return adapter.to_model(value)

        return value

    def _to_orm_value(self, orm_field: EntityField, value: t.Any) -> t.Any:
        """Convert a model field value to its ORM-side representation."""
        if value is not None and (adapter := orm_field.model_adapter):
            return adapter.to_orm(value)

        return value

    @t.overload
    def _build_model(self, projection: t.Literal['read']) -> type[ReadModel[EntityType]]: ...

    @t.overload
    def _build_model(self, projection: t.Literal['create']) -> type[CreateModel[EntityType]]: ...

    @t.overload
    def _build_model(self, projection: t.Literal['update']) -> type[UpdateModel[EntityType]]: ...

    def _build_model(self, projection: _ModelName) -> type[OrmModel[EntityType]]:
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to an entity class')

        model_fields: dict[str, tuple[t.Any, t.Any]] = {}
        orm_fields: dict[str, EntityField] = {}

        for name, orm_field in iter_fields(self._entity).items():
            spec = orm_field.spec

            if not _include_field(spec, projection):
                continue

            model_fields[name] = _build_model_field(
                self._model_field_type(orm_field),
                description=spec.description,
                model_field_info=orm_field.model_field_info,
                readonly=spec.readonly,
            )
            orm_fields[name] = orm_field

        model_base = _model_base(projection)
        class_name = f'{projection.capitalize()}Model'

        model = t.cast(
            type[OrmModel[EntityType]],
            pdt.create_model(
                f'{self._entity.__name__}{class_name}',
                __base__=model_base,
                __module__=self._entity.__module__,
                __qualname__=f'{self._entity.__qualname__}.{class_name}',
                **model_fields,
            ),
        )

        model._entity = self._entity
        model._orm_fields = orm_fields
        model._models_namespace = self

        return model


def _model_base(projection: _ModelName) -> type[OrmModel[t.Any]]:
    """Return the base class for a model projection."""
    if projection == 'read':
        return ReadModel

    if projection == 'create':
        return CreateModel

    if projection == 'update':
        return UpdateModel

    t.assert_never(projection)


def _include_field(spec: EntityFieldSpec, projection: _ModelName) -> bool:
    """Return whether a field belongs to a model projection."""
    if projection == 'read':
        return True

    if projection == 'create':
        return not spec.readonly

    if projection == 'update':
        return spec.mutable

    t.assert_never(projection)


def _build_model_field(
    model_type: t.Any,
    *,
    description: str = '',
    model_field_info: ModelFieldInfo | None = None,
    readonly: bool = False,
) -> tuple[t.Any, t.Any]:
    """Build the Pydantic declaration for a model field."""
    field_info = model_field_info if model_field_info is not None else ModelField()
    field_dict = field_info.asdict()

    metadata = field_dict['metadata']
    attributes = dict(field_dict['attributes'])

    if field_info.default is not PydanticUndefined:
        attributes['default'] = field_info.default
    elif _is_nullable(model_type):
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

    annotation = _make_annotated(model_type, metadata)

    return annotation, ModelField(**attributes)


def _is_nullable(annotation: t.Any) -> bool:
    """Return whether an annotation accepts `None`."""
    return type(None) in t.get_args(annotation)


def _make_nullable(annotation: t.Any) -> t.Any:
    """Return a nullable version of the annotation."""
    if _is_nullable(annotation):
        return annotation

    return annotation | None


def _make_annotated(annotation: t.Any, metadata: list[t.Any]) -> t.Any:
    """Return an `Annotated` type compatible with Python 3.10."""
    if not metadata:
        return annotation

    return t.Annotated[(annotation, *metadata)]
