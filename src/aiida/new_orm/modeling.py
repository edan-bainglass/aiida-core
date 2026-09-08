from __future__ import annotations

import dataclasses
import typing as t
from collections.abc import Callable, Iterable

import pydantic as pdt

__all__ = (
    'AttributesModelProjection',
    'AttributesModelSerializerInfo',
    'AttributesModelValidatorInfo',
    'EntityModelSerializerInfo',
    'EntityModelValidatorInfo',
    'ModelMetadata',
    'ModelProjection',
    'attributes_model_serializer',
    'attributes_model_validator',
    'entity_model_serializer',
    'entity_model_validator',
    'iter_attributes_model_serializers',
    'iter_attributes_model_validators',
    'iter_model_serializers',
    'iter_model_validators',
    'make_model_serializer',
    'make_model_validator',
    'model_metadata',
)

ModelProjection = t.Literal['read', 'create', 'update']

EntityModelProjection = ModelProjection
AttributesModelProjection = t.Literal['read', 'create']


@dataclasses.dataclass(frozen=True)
class ModelMetadata:
    """Pydantic annotation metadata scoped to selected entity model projections.

    If `projections` is `None`, the metadata applies to every projection in
    which the field itself participates.
    """

    metadata: tuple[t.Any, ...]
    projections: frozenset[ModelProjection] | None = None


def model_metadata(
    *metadata: t.Any,
    projections: Iterable[ModelProjection] | None = None,
) -> ModelMetadata:
    """Declare Pydantic annotation metadata for selected model projections."""
    return ModelMetadata(
        metadata=metadata,
        projections=None if projections is None else frozenset(projections),
    )


@dataclasses.dataclass(frozen=True)
class EntityModelValidatorInfo:
    """Configuration for a generated entity-model validator."""

    mode: t.Literal['before', 'after', 'wrap']
    projections: frozenset[ModelProjection] | None = None


@dataclasses.dataclass(frozen=True)
class EntityModelSerializerInfo:
    """Configuration for a generated entity-model serializer."""

    mode: t.Literal['plain', 'wrap']
    projections: frozenset[ModelProjection] | None = None


@dataclasses.dataclass(frozen=True)
class AttributesModelValidatorInfo:
    """Configuration for a generated Node attributes-model validator."""

    mode: t.Literal['before', 'after', 'wrap']
    projections: frozenset[AttributesModelProjection] | None = None


@dataclasses.dataclass(frozen=True)
class AttributesModelSerializerInfo:
    """Configuration for a generated Node attributes-model serializer."""

    mode: t.Literal['plain', 'wrap']
    projections: frozenset[AttributesModelProjection] | None = None


_EntityModelValidator = tuple[Callable[..., t.Any], EntityModelValidatorInfo]
_EntityModelSerializer = tuple[Callable[..., t.Any], EntityModelSerializerInfo]
_AttributesModelValidator = tuple[Callable[..., t.Any], AttributesModelValidatorInfo]
_AttributesModelSerializer = tuple[Callable[..., t.Any], AttributesModelSerializerInfo]


def entity_model_validator(
    *,
    mode: t.Literal['before', 'after', 'wrap'],
    projections: Iterable[EntityModelProjection] | None = None,
) -> Callable[[staticmethod], staticmethod]:
    """Declare a validator for generated entity models.

    The decorated method must be a `staticmethod`. The callback is later
    installed as a real Pydantic model validator on each generated model
    projection to which it applies.
    """
    info = EntityModelValidatorInfo(
        mode=mode,
        projections=None if projections is None else frozenset(projections),
    )

    def decorator(method: staticmethod) -> staticmethod:
        if not isinstance(method, staticmethod):
            raise TypeError('entity_model_validator must decorate a staticmethod')

        setattr(method.__func__, '__aiida_model_validator__', info)
        return method

    return decorator


def entity_model_serializer(
    *,
    mode: t.Literal['plain', 'wrap'],
    projections: Iterable[EntityModelProjection] | None = None,
) -> Callable[[staticmethod], staticmethod]:
    """Declare a serializer for generated entity models.

    The decorated method must be a `staticmethod`. The callback is later
    installed as a real Pydantic instance serializer on each generated model
    projection to which it applies.
    """
    info = EntityModelSerializerInfo(
        mode=mode,
        projections=None if projections is None else frozenset(projections),
    )

    def decorator(method: staticmethod) -> staticmethod:
        if not isinstance(method, staticmethod):
            raise TypeError('entity_model_serializer must decorate a staticmethod')

        setattr(method.__func__, '__aiida_model_serializer__', info)
        return method

    return decorator


def attributes_model_validator(
    *,
    mode: t.Literal['before', 'after', 'wrap'],
    projections: Iterable[AttributesModelProjection] | None = None,
) -> Callable[[staticmethod], staticmethod]:
    """Declare a validator for generated Node attributes models."""
    info = AttributesModelValidatorInfo(
        mode=mode,
        projections=None if projections is None else frozenset(projections),
    )

    def decorator(method: staticmethod) -> staticmethod:
        if not isinstance(method, staticmethod):
            raise TypeError('attributes_model_validator must decorate a staticmethod')

        setattr(method.__func__, '__aiida_attributes_model_validator__', info)
        return method

    return decorator


def attributes_model_serializer(
    *,
    mode: t.Literal['plain', 'wrap'],
    projections: Iterable[AttributesModelProjection] | None = None,
) -> Callable[[staticmethod], staticmethod]:
    """Declare a serializer for generated Node attributes models."""
    info = AttributesModelSerializerInfo(
        mode=mode,
        projections=None if projections is None else frozenset(projections),
    )

    def decorator(method: staticmethod) -> staticmethod:
        if not isinstance(method, staticmethod):
            raise TypeError('attributes_model_serializer must decorate a staticmethod')

        setattr(method.__func__, '__aiida_attributes_model_serializer__', info)
        return method

    return decorator


def iter_model_validators(entity: type) -> dict[str, _EntityModelValidator]:
    """Return effective entity-model validators across an entity hierarchy."""
    result: dict[str, _EntityModelValidator] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, staticmethod):
                function = value.__func__
                info = getattr(function, '__aiida_model_validator__', None)

                if isinstance(info, EntityModelValidatorInfo):
                    result[name] = (function, info)
                    continue

            result.pop(name, None)

    return result


def iter_model_serializers(entity: type) -> dict[str, _EntityModelSerializer]:
    """Return effective entity-model serializers across an entity hierarchy."""
    result: dict[str, _EntityModelSerializer] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, staticmethod):
                function = value.__func__
                info = getattr(function, '__aiida_model_serializer__', None)

                if isinstance(info, EntityModelSerializerInfo):
                    result[name] = (function, info)
                    continue

            result.pop(name, None)

    return result


def iter_attributes_model_validators(entity: type) -> dict[str, _AttributesModelValidator]:
    """Return effective Node attributes-model validators across an entity hierarchy."""
    result: dict[str, _AttributesModelValidator] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, staticmethod):
                function = value.__func__
                info = getattr(function, '__aiida_attributes_model_validator__', None)

                if isinstance(info, AttributesModelValidatorInfo):
                    result[name] = (function, info)
                    continue

            result.pop(name, None)

    return result


def iter_attributes_model_serializers(entity: type) -> dict[str, _AttributesModelSerializer]:
    """Return effective Node attributes-model serializers across an entity hierarchy."""
    result: dict[str, _AttributesModelSerializer] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, staticmethod):
                function = value.__func__
                info = getattr(function, '__aiida_attributes_model_serializer__', None)

                if isinstance(info, AttributesModelSerializerInfo):
                    result[name] = (function, info)
                    continue

            result.pop(name, None)

    return result


def make_model_validator(
    function: Callable[..., t.Any],
    *,
    mode: t.Literal['before', 'after', 'wrap'],
) -> t.Any:
    """Create a real Pydantic model validator delegating to a static callback."""
    if mode == 'before':

        @pdt.model_validator(mode='before')  # type: ignore[misc]
        @classmethod
        def validator(cls: type[pdt.BaseModel], value: t.Any) -> t.Any:
            return function(value)

        return validator

    if mode == 'after':

        @pdt.model_validator(mode='after')
        def validator(self: pdt.BaseModel) -> t.Any:
            return function(self)

        return validator

    if mode == 'wrap':

        @pdt.model_validator(mode='wrap')  # type: ignore[misc]
        @classmethod
        def validator(
            cls: type[pdt.BaseModel],
            value: t.Any,
            handler: pdt.ModelWrapValidatorHandler[t.Any],
        ) -> t.Any:
            return function(value, handler)

        return validator

    t.assert_never(mode)


def make_model_serializer(
    function: Callable[..., t.Any],
    *,
    mode: t.Literal['plain', 'wrap'],
) -> t.Any:
    """Create a real Pydantic model serializer delegating to a static callback."""
    if mode == 'plain':

        @pdt.model_serializer(mode='plain')
        def serializer(self: pdt.BaseModel) -> t.Any:
            return function(self)

        return serializer

    if mode == 'wrap':

        @pdt.model_serializer(mode='wrap')
        def serializer(  # type: ignore[misc]
            self: pdt.BaseModel,
            handler: pdt.SerializerFunctionWrapHandler,
        ) -> t.Any:
            return function(self, handler)

        return serializer

    t.assert_never(mode)
