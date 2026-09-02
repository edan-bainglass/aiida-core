from __future__ import annotations

import typing as t
from uuid import UUID

from aiida.common import exceptions
from aiida.orm import fields as qb_fields

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
