from __future__ import annotations

import pathlib
import typing as t
from uuid import UUID

from typing_extensions import Self

from aiida.common import exceptions
from aiida.orm import fields as qb_fields

from .cli_adapter import CliAdapter
from .entity import Entity
from .model_adapter import ModelAdapter


class EntityPkAdapter(ModelAdapter[Entity, int, qb_fields.QbNumericField]):
    """Represent an ORM entity by its primary key in models."""

    def __init__(self, entity_type: type[Entity]) -> None:
        self._entity_type = entity_type

    def to_model(self, value: Entity, *, context: dict[str, t.Any] | None = None) -> int:
        if value.pk is None:
            raise ValueError('entity must be stored to be represented by PK')
        return value.pk

    def to_entity(self, value: int) -> Entity:
        try:
            entity = self._entity_type.get_one(value)
        except exceptions.NotExistent:
            raise ValueError(f'entity with PK {value} does not exist') from None

        if entity is None:
            raise ValueError(f'entity with PK {value} does not exist')

        return entity


class StrUuidAdapter(ModelAdapter[str, UUID, qb_fields.QbStrField]):
    """Represent a UUID string in models."""

    def to_model(self, value: str, *, context: dict[str, t.Any] | None = None) -> UUID:
        return UUID(value)

    def to_entity(self, value: UUID) -> str:
        return str(value)


class PathStrAdapter(ModelAdapter[pathlib.PurePath, str, qb_fields.QbStrField]):
    """Represent a `pathlib.PurePath` object as a string in models."""

    def to_model(self, value: pathlib.PurePath, *, context: dict[str, t.Any] | None = None) -> str:
        return str(value)

    def to_entity(self, value: str) -> pathlib.PurePath:
        return pathlib.PurePath(value)


class LabeledEntity(t.Protocol):
    pk: int | None
    label: str

    @classmethod
    def get_one(cls, identifier: int | str) -> Self: ...


_EntityWithLabelT = t.TypeVar('_EntityWithLabelT', bound=LabeledEntity)


class LabelPkAdapter(CliAdapter[str, int]):
    """Represent a label as a primary key in CLI values."""

    def __init__(self, entity_type: type[_EntityWithLabelT]) -> None:
        self._entity_type = entity_type

    def to_model(self, value: str) -> int:
        entity = self._entity_type.get_one(value)

        if entity.pk is None:
            raise ValueError(f'{self._entity_type.__name__} with label {value!r} is not stored')

        return entity.pk

    def to_cli(self, value: int) -> str:
        entity = self._entity_type.get_one(value)

        if not hasattr(entity, 'label'):
            raise ValueError(f'{self._entity_type.__name__} with PK {value} does not have a label')

        return entity.label
