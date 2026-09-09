###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Module for all common top level AiiDA entity classes and methods"""

from __future__ import annotations

import abc
import typing as t
from enum import Enum
from functools import lru_cache

from typing_extensions import Self

from aiida.common import exceptions, log
from aiida.common.exceptions import InvalidOperation
from aiida.common.lang import call_with_super_check, classproperty, super_check, type_check
from aiida.manage import get_manager

if t.TYPE_CHECKING:
    from aiida.orm.implementation import BackendEntity, StorageBackend
    from aiida.orm.querybuilder import FilterType, OrderByType, QueryBuilder

__all__ = ('Collection', 'Entity', 'EntityTypes')

CollectionType = t.TypeVar('CollectionType', bound='Collection[t.Any]')
EntityType = t.TypeVar('EntityType', bound='Entity[t.Any, t.Any]')
BackendEntityType = t.TypeVar('BackendEntityType', bound='BackendEntity')


class EntityTypes(Enum):
    """Enum for referring to ORM entities in a backend-agnostic manner."""

    AUTHINFO = 'authinfo'
    COMMENT = 'comment'
    COMPUTER = 'computer'
    GROUP = 'group'
    LOG = 'log'
    NODE = 'node'
    USER = 'user'
    LINK = 'link'
    GROUP_NODE = 'group_node'


class Collection(abc.ABC, t.Generic[EntityType]):
    """Container class that represents the collection of objects of a particular entity type."""

    collection_type: t.ClassVar[str] = 'entities'

    @staticmethod
    @abc.abstractmethod
    def _entity_base_cls() -> type[EntityType]:
        """The allowed entity class or subclasses thereof."""

    @classmethod
    @lru_cache(maxsize=100)
    def get_cached(cls, entity_class: type[EntityType], backend: StorageBackend) -> Self:
        """Get the cached collection instance for the given entity class and backend.

        :param backend: the backend instance to get the collection for
        """
        from aiida.orm.implementation import StorageBackend

        type_check(backend, StorageBackend)
        return cls(entity_class, backend=backend)

    def __init__(self, entity_class: type[EntityType], backend: StorageBackend | None = None) -> None:
        """Construct a new entity collection.

        :param entity_class: the entity type e.g. User, Computer, etc
        :param backend: the backend instance to get the collection for, or use the default
        """
        from aiida.orm.implementation import StorageBackend

        type_check(backend, StorageBackend, allow_none=True)
        assert issubclass(entity_class, self._entity_base_cls())
        self._backend = backend or get_manager().get_profile_storage()
        self._entity_type = entity_class

    def __call__(self, backend: StorageBackend) -> Self:
        """Get or create a cached collection using a new backend."""
        if backend is self._backend:
            return self
        return self.get_cached(self.entity_type, backend=backend)

    @property
    def entity_type(self) -> type[EntityType]:
        """The entity type for this instance."""
        return self._entity_type

    @property
    def backend(self) -> StorageBackend:
        """Return the backend."""
        return self._backend

    def query(
        self,
        filters: FilterType | None = None,
        order_by: OrderByType | None = None,
        project: list[str] | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        subclassing: bool = True,
    ) -> QueryBuilder:
        """Get a query builder for the objects of this collection.

        :param filters: the keyword value pair filters to match
        :param order_by: a list of (key, direction) pairs specifying the sort order
        :param project: Optional projections.
        :param limit: the maximum number of results to return
        :param offset: number of initial results to be skipped
        :param subclassing: whether to match subclasses of the type as well.
        """
        from aiida.orm import querybuilder

        filters = filters or {}
        order_by = {self.entity_type: order_by} if order_by else {}

        query = querybuilder.QueryBuilder(backend=self._backend, limit=limit, offset=offset)
        query.append(self.entity_type, project=project, filters=filters, subclassing=subclassing)
        query.order_by([order_by])
        return query

    def get(self, **filters: t.Any) -> EntityType:
        """Get a single collection entry that matches the filter criteria.

        :param filters: the filters identifying the object to get

        :return: the entry
        """
        res = self.query(filters=filters)
        return res.one()[0]

    def find(
        self,
        filters: FilterType | None = None,
        order_by: OrderByType | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[EntityType]:
        """Find collection entries matching the filter criteria.

        :param filters: the keyword value pair filters to match
        :param order_by: a list of (key, direction) pairs specifying the sort order
        :param limit: the maximum number of results to return
        :param offset: number of initial results to be skipped

        :return: a list of resulting matches
        """
        query = self.query(filters=filters, order_by=order_by, limit=limit, offset=offset)
        return query.all(flat=True)

    def all(self) -> list[EntityType]:
        """Get all entities in this collection.

        :return: A list of all entities
        """
        return self.query().all(flat=True)

    def count(self, filters: FilterType | None = None) -> int:
        """Count entities in this collection according to criteria.

        :param filters: the keyword value pair filters to match

        :return: The number of entities found using the supplied criteria
        """
        return self.query(filters=filters).count()


class Entity(abc.ABC, t.Generic[BackendEntityType, CollectionType]):
    """An AiiDA entity"""

    _CLS_COLLECTION: type[CollectionType] = Collection  # type: ignore[assignment]
    _logger = log.AIIDA_LOGGER.getChild('orm.entities')

    identity_field = 'pk'

    def __init__(self, backend_entity: BackendEntityType) -> None:
        """:param backend_entity: the backend model supporting this entity"""
        self._backend_entity = backend_entity
        call_with_super_check(self.initialize)

    def serialize(
        self,
        *,
        context: dict[str, t.Any] | None = None,
        minimal: bool = False,
        schema: t.Literal['read', 'write'] | None = None,
        mode: t.Literal['json', 'python'] = 'python',
        exclude_none: bool = False,
    ) -> dict[str, t.Any]:
        """Serialize the entity instance to JSON.

        :param context: Optional context dictionary to pass to `orm_to_model` callables.
        :param minimal: Whether to exclude potentially large value fields.
        :param schema: The schema to use for serialization. Defaults to 'read' if stored, 'write' otherwise.
        :param mode: The serialization mode, either 'json' or 'python' (default). JSON-based clients (e.g., REST APIs)
            should use 'json' mode.
        :param exclude_none: Whether to exclude fields with a value of `None`.
        :return: A dictionary that can be serialized to JSON.
        :raises UnsupportedSchemaError: if the provided schema is not supported for this entity.
        """
        return self.to_model(context=context, minimal=minimal, schema=schema).model_dump(
            mode=mode,
            exclude_unset=minimal,
            exclude_none=exclude_none,
        )

    @classproperty
    def collection(cls) -> CollectionType:  # noqa: N805
        """Get a collection for objects of this type, with the default backend.

        :return: an object that can be used to access entities of this type
        """
        return cls._CLS_COLLECTION.get_cached(cls, get_manager().get_profile_storage())

    @classmethod
    def get_collection(cls, backend: StorageBackend) -> CollectionType:
        """Get a collection for objects of this type for a given backend.

        .. note:: Use the ``collection`` class property instead if the currently loaded backend or backend of the
            default profile should be used.

        :param backend: The backend of the collection to use.
        :return: A collection object that can be used to access entities of this type.
        """
        return cls._CLS_COLLECTION.get_cached(cls, backend)

    def __eq__(self, other: t.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False

        if hasattr(self, 'uuid'):
            return self.uuid == other.uuid  # type: ignore[attr-defined]

        return super().__eq__(other)

    def __getstate__(self) -> t.NoReturn:
        """Prevent an ORM entity instance from being pickled."""
        raise InvalidOperation('pickling of AiiDA ORM instances is not supported.')

    @super_check
    def initialize(self) -> None:
        """Initialize instance attributes.

        This will be called after the constructor is called or an entity is created from an existing backend entity.
        """

    @property
    def logger(self) -> log.AiidaLoggerType:
        """Return the internal logger."""
        try:
            return self._logger
        except AttributeError:
            raise exceptions.InternalError('No self._logger configured for {}!')

    @property
    def pk(self) -> int | None:
        """Return the primary key for this entity.

        This identifier is guaranteed to be unique amongst entities of the same type for a single backend instance.

        :return: the entity's principal key
        """
        return self._backend_entity.id

    def store(self) -> Self:
        """Store the entity."""
        self._backend_entity.store()
        return self

    @property
    def is_stored(self) -> bool:
        """Return whether the entity is stored."""
        return self._backend_entity.is_stored

    @property
    def backend(self) -> StorageBackend:
        """Get the backend for this entity"""
        return self._backend_entity.backend

    @property
    def backend_entity(self) -> BackendEntityType:
        """Get the implementing class for this object"""
        return self._backend_entity


def from_backend_entity(cls: type[EntityType], backend_entity: BackendEntity) -> EntityType:
    """Construct an entity from a backend entity instance

    :param backend_entity: the backend entity

    :return: an AiiDA entity instance
    """
    from aiida.orm.implementation.entities import BackendEntity

    type_check(backend_entity, BackendEntity)
    entity = cls.__new__(cls)
    entity._backend_entity = backend_entity
    call_with_super_check(entity.initialize)
    return entity
