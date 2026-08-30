from uuid import UUID

from entity import Entity
from model_adapter import ModelAdapter


class EntityPkAdapter(ModelAdapter[Entity, int]):
    """Represent an ORM entity by its primary key in models."""

    def __init__(self, entity_type: type[Entity]) -> None:
        self._entity_type = entity_type

    def to_model(self, value: Entity) -> int:
        if value.pk is None:
            raise ValueError('entity must be stored to be represented by PK')
        return value.pk

    def to_orm(self, value: int) -> Entity:
        return self._entity_type.get_one(value)


class StrUuidAdapter(ModelAdapter[str, UUID]):
    """Represent a UUID string in models."""

    def to_model(self, value: str) -> UUID:
        return UUID(value)

    def to_orm(self, value: UUID) -> str:
        return str(value)
