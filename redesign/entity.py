from __future__ import annotations

import abc
import typing as t

from fields import field
from models import ModelsNamespace
from plumpy.base import call_with_super_check, super_check
from typing_extensions import Self

from aiida.common.lang import type_check
from aiida.orm.implementation import BackendEntity

_EntityT = t.TypeVar('_EntityT', bound='Entity')
_BackendEntityT = t.TypeVar('_BackendEntityT', bound=BackendEntity)


class Entity(abc.ABC, t.Generic[_BackendEntityT]):
    models: ModelsNamespace[Self] = ModelsNamespace()

    def __init__(self, backend_entity: _BackendEntityT, **kwargs):
        super().__init__(**kwargs)
        self._backend_entity = backend_entity

    @field(
        backend_key='id',
        readonly=True,
        required_once_stored=True,
    )
    def pk(self) -> int | None:
        """The primary key of the entity."""
        return self._backend_entity.pk

    @property
    def backend_entity(self) -> _BackendEntityT:
        """Get the implementing class for this object"""
        return self._backend_entity

    @property
    def is_stored(self) -> bool:
        """Return whether the entity is stored."""
        return self._backend_entity.is_stored

    def store(self) -> Self:
        """Store the entity."""
        self._backend_entity.store()
        return self

    @classmethod
    def get_one(cls, identifier: int | str) -> Self | None:
        """Get an entity by identifier."""
        raise NotImplementedError('get_one must be implemented in subclasses')

    @super_check
    def _initialize(self) -> None:
        """Initialize instance attributes.

        This will be called after the constructor is called or an entity is created from an existing backend entity.
        """


def from_backend_entity(cls: type[_EntityT], backend_entity: BackendEntity) -> _EntityT:
    """Construct an entity from a backend entity instance

    :param backend_entity: the backend entity

    :return: an AiiDA entity instance
    """

    type_check(backend_entity, BackendEntity)
    entity = cls.__new__(cls)
    entity._backend_entity = backend_entity
    call_with_super_check(entity._initialize)
    return entity
