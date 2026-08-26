import typing as t

from entity import Entity
from fields import ModelAdapter


class EntityPkAdapter(ModelAdapter['Entity', int]):
    """Represent an ORM entity by its primary key in models."""

    model_type: t.ClassVar[t.Any] = int

    def __init__(self, entity_type: type[Entity]) -> None:
        self._entity_type = entity_type

    def to_model(self, value: Entity) -> int:
        return value.pk

    def to_orm(self, value: int) -> Entity:
        return self._entity_type.get_one(value)
