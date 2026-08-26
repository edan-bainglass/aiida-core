from __future__ import annotations

import abc
import typing as t

from fields import field
from models import ModelsNamespace
from plumpy.base import call_with_super_check, super_check
from typing_extensions import Self

from aiida.common.lang import type_check
from aiida.orm.implementation import BackendEntity

EntityType = t.TypeVar('EntityType', bound='Entity')
BackendEntityType = t.TypeVar('BackendEntityType', bound=BackendEntity)


class Entity(abc.ABC, t.Generic[BackendEntityType]):
    models: ModelsNamespace[Self] = ModelsNamespace()

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

    @property
    def backend_entity(self) -> BackendEntityType:
        """Get the implementing class for this object"""
        return self._backend_entity

    @property
    def is_stored(self) -> bool:
        """Return whether the entity is stored."""
        return self._backend_entity.is_stored

    @classmethod
    def get_one(cls, pk: int) -> Self | None:
        """Get an entity by primary key."""
        raise NotImplementedError('get_one must be implemented in subclasses')

    @super_check
    def _initialize(self) -> None:
        """Initialize instance attributes.

        This will be called after the constructor is called or an entity is created from an existing backend entity.
        """


def from_backend_entity(cls: type[EntityType], backend_entity: BackendEntity) -> EntityType:
    """Construct an entity from a backend entity instance

    :param backend_entity: the backend entity

    :return: an AiiDA entity instance
    """

    type_check(backend_entity, BackendEntity)
    entity = cls.__new__(cls)
    entity._backend_entity = backend_entity
    call_with_super_check(entity._initialize)
    return entity
