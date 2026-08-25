from __future__ import annotations

import typing as t

import pydantic as pdt
from fields import (
    FieldSpec,
    ModelField,
    OrmField,
    iter_fields,
)

if t.TYPE_CHECKING:
    from entity import Entity


__all__ = (
    'CreateModel',
    'ModelsNamespace',
    'OrmModel',
    'ReadModel',
    'UnsupportedModelError',
    'UpdateModel',
)


_EntityT = t.TypeVar('_EntityT', bound='Entity')
_ModelName = t.Literal['read', 'create', 'update']


class OrmModel(pdt.BaseModel, t.Generic[_EntityT]):
    """Base class for dynamically generated ORM models."""

    model_config = pdt.ConfigDict(
        extra='forbid',
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    # Shadowing Pydantic's `from_orm` classmethod to disable
    # its default (and deprecated) implementation
    from_orm: t.ClassVar[None] = None

    # Set on each dynamically generated model class.
    _entity: t.ClassVar[type[Entity]]
    _orm_fields: t.ClassVar[dict[str, OrmField]]

    @classmethod
    def field_spec(cls, name: str) -> FieldSpec:
        """Return the canonical ORM specification for a model field."""
        return cls._orm_fields[name].spec

    @classmethod
    def _from_orm_field_values(
        cls,
        entity: _EntityT,
    ) -> dict[str, t.Any]:
        """Convert ORM field values to model-side representations."""
        values: dict[str, t.Any] = {}

        for name, orm_field in cls._orm_fields.items():
            value = getattr(entity, name)

            if adapter := orm_field.model_adapter:
                value = adapter.to_model(value)

            values[name] = value

        return values

    def _to_orm_field_values(
        self,
        *,
        only_set: bool = False,
    ) -> dict[str, t.Any]:
        """Convert model field values to ORM-side representations."""
        names: t.Iterable[str]

        if only_set:
            names = self.model_fields_set
        else:
            names = self.__class__.model_fields

        values: dict[str, t.Any] = {}

        for name in names:
            orm_field = self.__class__._orm_fields[name]
            value = getattr(self, name)

            if adapter := orm_field.model_adapter:
                value = adapter.to_orm(value)

            values[name] = value

        return values


class ReadModel(OrmModel[_EntityT]):
    """Read projection of an ORM entity."""

    @classmethod
    def from_orm(
        cls,
        entity: _EntityT,
    ) -> t.Self:
        """Create a read model from an ORM entity."""
        return cls.model_validate(cls._from_orm_field_values(entity))


class CreateModel(OrmModel[_EntityT]):
    """Input projection for constructing an ORM entity."""

    def to_orm(self) -> _EntityT:
        """Construct an ORM entity from this model."""
        return t.cast(
            _EntityT,
            self.__class__._entity(**self._to_orm_field_values()),
        )


class UpdateModel(OrmModel[_EntityT]):
    """PATCH-like projection for mutating an ORM entity."""

    def apply(self, entity: _EntityT) -> _EntityT:
        """Apply explicitly set values to an ORM entity."""
        for name, value in self._to_orm_field_values(
            only_set=True,
        ).items():
            setattr(entity, name, value)

        return entity


class UnsupportedModelError(AttributeError):
    """Raised when an unsupported model projection is requested."""


class ModelsNamespace(t.Generic[_EntityT]):
    """Lazily generated model projections for one entity class."""

    _names: t.ClassVar[set[_ModelName]] = {
        'read',
        'create',
        'update',
    }

    def __init__(self) -> None:
        self._entity: type[_EntityT] | None = None
        self._models: dict[
            type[_EntityT],
            dict[_ModelName, type[OrmModel[t.Any]]],
        ] = {}

    @t.overload
    def __get__(
        self,
        instance: None,
        owner: type[_EntityT],
    ) -> ModelsNamespace[_EntityT]: ...

    @t.overload
    def __get__(
        self,
        instance: object,
        owner: type[_EntityT] | None = None,
    ) -> ModelsNamespace[_EntityT]: ...

    def __get__(
        self,
        instance: object | None,
        owner: type[_EntityT] | None = None,
    ) -> ModelsNamespace[_EntityT]:
        if owner is None:
            raise AttributeError('models must be accessed through an entity class')

        namespace = type(self)()
        namespace._entity = owner
        namespace._models = self._models

        return namespace

    @t.overload
    def __getattr__(
        self,
        name: t.Literal['read'],
    ) -> type[ReadModel[_EntityT]]: ...

    @t.overload
    def __getattr__(
        self,
        name: t.Literal['create'],
    ) -> type[CreateModel[_EntityT]]: ...

    @t.overload
    def __getattr__(
        self,
        name: t.Literal['update'],
    ) -> type[UpdateModel[_EntityT]]: ...

    def __getattr__(
        self,
        name: str,
    ) -> type[OrmModel[t.Any]]:
        if name not in self._names:
            models = ', '.join(sorted(self._names))
            raise UnsupportedModelError(f"'{name}' model is not supported; valid projections: {models}")

        if self._entity is None:
            raise RuntimeError('model namespace is not bound to an entity class')

        projection = t.cast(_ModelName, name)
        models = self._models.setdefault(self._entity, {})

        if projection not in models:
            models[projection] = self._build_model(projection)

        return models[projection]

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | self._names)

    def _build_model(
        self,
        projection: _ModelName,
    ) -> type[OrmModel[t.Any]]:
        if self._entity is None:
            raise RuntimeError('model namespace is not bound to an entity class')

        model_fields: dict[str, tuple[t.Any, t.Any]] = {}
        orm_fields: dict[str, OrmField] = {}

        for name, orm_field in iter_fields(self._entity).items():
            spec = orm_field.spec

            if not _include_field(spec, projection):
                continue

            model_fields[name] = _build_model_field(
                orm_field,
                spec,
            )
            orm_fields[name] = orm_field

        model_base = _model_base(projection)
        class_name = f'{projection.capitalize()}Model'

        model = t.cast(
            type[OrmModel[_EntityT]],
            pdt.create_model(
                f'{self._entity.__name__}{class_name}',
                __base__=model_base,
                __module__=self._entity.__module__,
                __qualname__=(f'{self._entity.__qualname__}.{class_name}'),
                **model_fields,
            ),
        )

        model._entity = self._entity
        model._orm_fields = orm_fields

        return t.cast(type[OrmModel[t.Any]], model)


def _model_base(
    projection: _ModelName,
) -> type[OrmModel[t.Any]]:
    """Return the base class for a model projection."""
    if projection == 'read':
        return ReadModel

    if projection == 'create':
        return CreateModel

    if projection == 'update':
        return UpdateModel

    t.assert_never(projection)


def _include_field(
    spec: FieldSpec,
    projection: _ModelName,
) -> bool:
    """Return whether a field belongs to a model projection."""
    if projection == 'read':
        return True

    if projection == 'create':
        return not spec.readonly

    if projection == 'update':
        return spec.mutable

    t.assert_never(projection)


def _build_model_field(
    orm_field: OrmField,
    spec: FieldSpec,
) -> tuple[t.Any, t.Any]:
    """Build the Pydantic declaration for an ORM field."""

    model_type = orm_field.model_adapter.model_type if orm_field.model_adapter is not None else spec.value_type

    field_info = orm_field.model_field_info if orm_field.model_field_info is not None else ModelField()

    field_dict = field_info.asdict()

    metadata = field_dict['metadata']
    attributes = dict(field_dict['attributes'])

    # The getter docstring provides the default model description.
    # Explicit Pydantic configuration wins.
    if attributes['description'] is None and spec.description:
        attributes['description'] = spec.description

    # Expose read-only semantics to JSON Schema only when true.
    if spec.readonly:
        json_schema_extra = attributes['json_schema_extra']

        if json_schema_extra is None:
            json_schema_extra = {}
        elif not isinstance(json_schema_extra, dict):
            raise TypeError('callable `json_schema_extra` is not supported for read-only ORM fields')
        else:
            json_schema_extra = dict(json_schema_extra)

        json_schema_extra.setdefault('readOnly', True)
        attributes['json_schema_extra'] = json_schema_extra

    annotation = _make_annotated(
        model_type,
        metadata,
    )

    return annotation, ModelField(**attributes)


def _make_annotated(
    annotation: t.Any,
    metadata: list[t.Any],
) -> t.Any:
    """Return an `Annotated` type compatible with Python 3.10."""
    if not metadata:
        return annotation

    return t.Annotated[(annotation, *metadata)]
