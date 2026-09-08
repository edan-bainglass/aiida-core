from __future__ import annotations

import datetime
import functools
import typing as t
from uuid import UUID

import pydantic as pdt
from importlib_metadata import EntryPoint
from typing_extensions import Self

from aiida import orm
from aiida.common import exceptions
from aiida.common.lang import classproperty
from aiida.common.links import LinkType
from aiida.common.log import AIIDA_LOGGER
from aiida.manage import get_manager
from aiida.new_orm.adapters import EntityPkAdapter, StrUuidAdapter
from aiida.new_orm.attributes import attributes_column
from aiida.new_orm.columns import column
from aiida.new_orm.computer import Computer
from aiida.new_orm.entity import Entity, from_backend_entity
from aiida.new_orm.node_models import NodeModelsNamespace
from aiida.new_orm.user import User
from aiida.orm.implementation import BackendNode
from aiida.orm.nodes.caching import NodeCaching
from aiida.orm.nodes.links import NodeLinks
from aiida.orm.nodes.node import NodeBase
from aiida.orm.utils.node import get_type_string_from_class

if t.TYPE_CHECKING:
    from aiida.common.log import AiidaLoggerType
    from aiida.orm.implementation import StorageBackend

__all__ = ('Node',)


class Node(Entity[BackendNode]):
    """ORM representation of an AiiDA node."""

    models: NodeModelsNamespace[Self] = NodeModelsNamespace()

    _CLS_NODE_LINKS = NodeLinks
    _CLS_NODE_CACHING = NodeCaching

    __plugin_type_string: t.ClassVar[str]

    _extra_attributes: t.ClassVar[t.Literal['allow', 'forbid']] = 'forbid'

    # This will be set by the metaclass call but we set default
    _logger: AiidaLoggerType = AIIDA_LOGGER

    # A tuple of attribute names that can be updated even after node is stored
    # Requires Sealable mixin, but needs empty tuple for base class
    _updatable_attributes: tuple[str, ...] = tuple()

    # A tuple of attribute names that will be ignored when creating the hash.
    _hash_ignored_attributes: tuple[str, ...] = tuple()

    # Flag that determines whether the class can be cached.
    _cachable = False

    # Flag that determines whether the class can be stored.
    _storable = False
    _unstorable_message = 'only Data, WorkflowNode, CalculationNode or their subclasses can be stored'

    def __init__(
        self,
        label: str = '',
        description: str = '',
        extras: dict | None = None,
        attributes: dict | None = None,
        computer: Computer | None = None,
        user: User | None = None,
        backend: StorageBackend | None = None,
    ):
        backend = backend or get_manager().get_profile_storage()

        if computer is not None and not computer.is_stored:
            raise ValueError('the computer is not stored')

        backend_computer = computer.backend_entity if computer else None
        user = user if user else backend.default_user  # type: ignore[assignment]

        if user is None:
            raise ValueError('the user cannot be None')

        backend_entity = backend.nodes.create(
            label=label,
            description=description,
            node_type=self.class_node_type,
            user=user.backend_entity,
            computer=backend_computer,
        )

        super().__init__(backend_entity)

        if attributes:
            self.base.attributes.set_many(attributes)

        if extras:
            self.base.extras.set_many(extras)

    def __init_subclass__(
        cls,
        *,
        extra_attributes: t.Literal[
            'allow',
            'forbid',
        ] = 'forbid',
        **kwargs: t.Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        cls._extra_attributes = extra_attributes

    def __eq__(self, other: t.Any) -> bool:
        """Fallback equality comparison by uuid (can be overwritten by specific types)"""
        if isinstance(other, Node) and self.uuid == other.uuid:
            return True
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Python-Hash: Implementation that is compatible with __eq__"""
        return int(UUID(self.uuid))

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self!s}>'

    def __str__(self) -> str:
        if not self.is_stored:
            return f'uuid: {self.uuid} (unstored)'

        return f'uuid: {self.uuid} (pk: {self.pk})'

    def __copy__(self) -> t.NoReturn:
        """Copying a Node is not supported in general, but only for the Data sub class."""
        raise exceptions.InvalidOperation('copying a base Node is not supported')

    def __deepcopy__(self, memo: t.Any) -> t.NoReturn:
        """Deep copying a Node is not supported in general, but only for the Data sub class."""
        raise exceptions.InvalidOperation('deep copying a base Node is not supported')

    @column(
        updatable=True,
        model_field_info=pdt.fields.FieldInfo(default=''),
    )
    def label(self) -> str:
        """The label of the node."""
        return self._backend_entity.label

    @label.setter
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @column(
        updatable=True,
        model_field_info=pdt.fields.FieldInfo(default=''),
    )
    def description(self) -> str:
        """The description of the node."""
        return self._backend_entity.description

    @description.setter
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @column(
        updatable=True,
        may_be_large=True,
        model_field_info=pdt.fields.FieldInfo(default_factory=dict),
    )
    def extras(self) -> dict[str, t.Any]:
        """The extras of the node."""
        return self.base.extras.all

    @extras.setter
    def extras(self, value: dict[str, t.Any]) -> None:
        self.base.extras.reset(value)

    @attributes_column
    def attributes(self) -> dict[str, t.Any]:
        """The attributes of the node."""
        return self.base.attributes.all

    @attributes.setter
    def attributes(self, value: dict[str, t.Any]) -> None:
        self.base.attributes.reset(value)

    @column(
        readonly=True,
        model_field_info=pdt.fields.FieldInfo(description='The PK of the associated user.'),
        model_adapter=EntityPkAdapter(User),
    )
    def user(self) -> User:
        """The user associated with the node."""
        return from_backend_entity(User, self._backend_entity.user)

    @column(
        model_field_info=pdt.fields.FieldInfo(
            default=None,
            description='The PK of the associated computer.',
        ),
        model_adapter=EntityPkAdapter(Computer),
    )
    def computer(self) -> Computer | None:
        """The computer associated with the node."""
        if self.backend_entity.computer:
            return from_backend_entity(Computer, self.backend_entity.computer)

        return None

    @column(
        readonly=True,
        model_adapter=StrUuidAdapter(),
    )
    def uuid(self) -> str:
        """The UUID of the node."""
        return self._backend_entity.uuid

    @column(readonly=True)
    def node_type(self) -> str:
        """The type of the node."""
        return self._backend_entity.node_type

    @column(readonly=True)
    def process_type(self) -> str | None:
        """The process type of the node."""
        return self._backend_entity.process_type

    @column(readonly=True)
    def ctime(self) -> datetime.datetime:
        """The creation time of the node."""
        return self._backend_entity.ctime

    @column(readonly=True)
    def mtime(self) -> datetime.datetime:
        """The last modification time of the node."""
        return self._backend_entity.mtime

    @column(
        readonly=True,
        may_be_large=True,
        model_field_info=pdt.fields.FieldInfo(default_factory=dict),
    )
    def repository_metadata(self) -> dict[str, t.Any]:
        """The repository metadata of the node."""
        return self.base.repository.metadata

    @functools.cached_property
    def base(self) -> NodeBase:
        """Return the base of the node."""
        return NodeBase(self)  # type: ignore[arg-type]

    @classproperty
    def entry_point(cls: type[Node]) -> EntryPoint | None:  # noqa: N805
        """Return the entry point associated this node class."""
        from aiida.plugins.entry_point import get_entry_point_from_class

        return get_entry_point_from_class(cls.__module__, cls.__name__)[1]

    @classproperty
    def class_node_type(cls: type[Node]) -> str:  # noqa: N805
        return cls._plugin_type_string

    @classmethod
    def get_one(cls, identifier: int | str) -> Node:
        """Get a node by identifier (PK or UUID)."""
        try:
            return orm.load_node(identifier)  # type: ignore[return-value]
        except exceptions.NotExistent:
            raise ValueError(f'Node with identifier {identifier} does not exist') from None

    def store_all(self) -> Self:
        """Store the node, together with all input links.

        Unstored nodes from cached incoming linkswill also be stored.
        """
        if self.is_stored:
            raise exceptions.ModificationNotAllowed(f'Node<{self.pk}> is already stored')

        # For each node of a cached incoming link, check that all its incoming links are stored
        for link_triple in self.base.links.incoming_cache:
            link_triple.node._verify_are_parents_stored()

        for link_triple in self.base.links.incoming_cache:
            if not link_triple.node.is_stored:
                link_triple.node.store()

        return self.store()

    def store(self) -> Self:
        """Store the node in the database while saving its attributes and repository directory.

        After being called attributes cannot be changed anymore! Instead, extras can be changed only AFTER calling
        this store() function.
        """
        if not self.is_stored:
            # Call `_validate_storability` directly and not in `_validate` in case sub class forgets to call the super.
            self._validate_storability()
            self._validate()

            # Verify that parents are already stored. Raises if this is not the case.
            self._verify_are_parents_stored()

            # Clean the values on the backend node *before* computing the hash in `_get_same_node`. This will allow
            # us to set `clean=False` if we are storing normally, since the values will already have been cleaned
            self._backend_entity.clean_values()

            # Retrieve the cached node if ``should_use_cache`` returns True
            same_node = self.base.caching._get_same_node() if self.base.caching.should_use_cache() else None

            if same_node is not None:
                self._store_from_cache(same_node)  # type: ignore[arg-type]
            else:
                self._store(clean=True)

            if self.backend.autogroup.is_to_be_grouped(self):
                group = self.backend.autogroup.get_or_create_group()
                group.add_nodes(self)  # type: ignore[arg-type]

        return self

    @classproperty
    def _plugin_type_string(cls: type[Node]) -> str:  # noqa: N805
        if not hasattr(cls, '__plugin_type_string'):
            cls.__plugin_type_string = get_type_string_from_class(cls.__module__, cls.__name__)
        return cls.__plugin_type_string

    def _store(self, clean: bool = True) -> Self:
        """Store the node in the database while saving its attributes and repository directory."""
        self.base.repository._store()

        links = self.base.links.incoming_cache
        self._backend_entity.store(links, clean=clean)

        self.base.links.incoming_cache = []
        self.base.caching.rehash()

        return self

    def _verify_are_parents_stored(self) -> None:
        """Verify that all `parent` nodes are already stored."""
        for link_triple in self.base.links.incoming_cache:
            if not link_triple.node.is_stored:
                raise exceptions.ModificationNotAllowed(
                    f'Cannot store because source node of link triple {link_triple} is not stored'
                )

    def _store_from_cache(self, cache_node: Node) -> None:
        """Store this node from an existing cache node."""
        from aiida.orm.utils.mixins import Sealable

        assert self.node_type == cache_node.node_type

        # Make sure the node doesn't have any RETURN links
        if cache_node.base.links.get_outgoing(link_type=LinkType.RETURN).all():
            raise ValueError('Cannot use cache from nodes with RETURN links.')

        self.label = cache_node.label  # type: ignore[method-assign]
        self.description = cache_node.description  # type: ignore[method-assign]

        # Make sure to reinitialize the repository instance of the clone to that of the source node.
        self.base.repository._copy(cache_node.base.repository)

        for key, value in cache_node.base.attributes.all.items():
            if key != Sealable.SEALED_KEY:
                self.base.attributes.set(key, value)

        self._store(clean=False)
        self._add_outputs_from_cache(cache_node)
        self.base.extras.set(self.base.caching.CACHED_FROM_KEY, cache_node.uuid)

    def _add_outputs_from_cache(self, cache_node: Node) -> None:
        """Replicate the output links and nodes from the cached node onto this node."""
        for entry in cache_node.base.links.get_outgoing(link_type=LinkType.CREATE):
            new_node = entry.node.clone()
            new_node.base.links.add_incoming(self, link_type=LinkType.CREATE, link_label=entry.link_label)
            new_node.store()

    def _check_mutability_attributes(self, keys: list[str] | None = None) -> None:
        """Check if the entity is mutable and raise an exception if not.

        This is called from `NodeAttributes` methods that modify the attributes.

        :param keys: the keys that will be mutated, or all if None
        """
        if self.is_stored:
            raise exceptions.ModificationNotAllowed('the attributes of a stored entity are immutable')

    def _validate(self) -> None:
        """Validate information stored in Node object."""

    def _validate_storability(self) -> None:
        """Verify that the current node is allowed to be stored."""
        from aiida.plugins.entry_point import is_registered_entry_point

        if not self._storable:
            raise exceptions.StoringNotAllowed(self._unstorable_message)

        if not is_registered_entry_point(self.__module__, self.__class__.__name__, groups=('aiida.node', 'aiida.data')):
            raise exceptions.StoringNotAllowed(
                f'class `{self.__module__}:{self.__class__.__name__}` does not have a registered entry point. '
                'Check that the corresponding plugin is installed '
                'and that the entry point shows up in `verdi plugin list`.'
            )
