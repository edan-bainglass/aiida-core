from __future__ import annotations

import abc
import typing as t

from fields import field
from models import ModelsNamespace

from aiida.orm.implementation import BackendEntity

EntityType = t.TypeVar('EntityType', bound='Entity')
BackendEntityType = t.TypeVar('BackendEntityType', bound=BackendEntity)


class Entity(abc.ABC, t.Generic[BackendEntityType]):
    models: ModelsNamespace[Entity[BackendEntityType]] = ModelsNamespace()

    def __init__(self, backend_entity: BackendEntityType, **kwargs):
        super().__init__(**kwargs)
        self._backend_entity = backend_entity

    @field(
        backend_key='id',
        readonly=True,
    )
    def pk(self) -> int:
        """The primary key of the entity."""
        return self._backend_entity.pk
