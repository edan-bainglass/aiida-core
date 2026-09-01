from __future__ import annotations

import datetime
import functools
import typing as t

from typing_extensions import Self

from aiida.common import exceptions
from aiida.common.lang import classproperty
from aiida.manage import get_manager
from aiida.orm.implementation import BackendNode, StorageBackend
from aiida.orm.nodes.node import NodeBase
from aiida.orm.utils.node import get_type_string_from_class

from .adapters import EntityPkAdapter, StrUuidAdapter
from .attributes import attributes_field
from .computer import Computer
from .entity import Entity, from_backend_entity
from .fields import ModelFieldInfo, field
from .node_models import NodeModelsNamespace
from .user import User


class Node(Entity[BackendNode]):
    models: NodeModelsNamespace[Self] = NodeModelsNamespace()

    __plugin_type_string: t.ClassVar[str]

    _extra_attributes: t.ClassVar[t.Literal['allow', 'forbid']] = 'forbid'

    def __init__(
        self,
        label: str = '',
        description: str = '',
        extras: dict | None = None,
        attributes: dict | None = None,
        computer: Computer | None = None,
        user: User | None = None,
        backend: StorageBackend | None = None,
        **kwargs,
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
            **kwargs,
        )

        super().__init__(backend_entity, **kwargs)

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
        **kwargs,
    ) -> None:
        super().__init_subclass__(**kwargs)
        cls._extra_attributes = extra_attributes

    @field(
        updatable=True,
        model_field_info=ModelFieldInfo(default=''),
    )
    def label(self) -> str:
        """The label of the node."""
        return self._backend_entity.label

    @label.setter  # type: ignore[no-redef]
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @field(
        updatable=True,
        model_field_info=ModelFieldInfo(default=''),
    )
    def description(self) -> str:
        """The description of the node."""
        return self._backend_entity.description

    @description.setter  # type: ignore[no-redef]
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @field(
        updatable=True,
        model_field_info=ModelFieldInfo(default_factory=dict),
    )
    def extras(self) -> dict[str, t.Any]:
        """The extras of the node."""
        return self.base.extras.all

    @extras.setter  # type: ignore[no-redef]
    def extras(self, value: dict[str, t.Any]) -> None:
        self.base.extras.reset(value)

    @attributes_field
    def attributes(self) -> dict[str, t.Any]:
        """The attributes of the node."""
        return self.base.attributes.all

    @attributes.setter  # type: ignore[no-redef]
    def attributes(self, value: dict[str, t.Any]) -> None:
        self.base.attributes.reset(value)

    @field(
        readonly=True,
        model_field_info=ModelFieldInfo(description='The PK of the associated user.'),
        model_adapter=EntityPkAdapter(User),
    )
    def user(self) -> User:
        """The user associated with the node."""
        return from_backend_entity(User, self._backend_entity.user)

    @field(
        model_field_info=ModelFieldInfo(
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

    @field(
        readonly=True,
        model_adapter=StrUuidAdapter(),
    )
    def uuid(self) -> str:
        """The UUID of the node."""
        return self._backend_entity.uuid

    @field(readonly=True)
    def node_type(self) -> str:
        """The type of the node."""
        return self._backend_entity.node_type

    @field(readonly=True)
    def process_type(self) -> str | None:
        """The process type of the node."""
        return self._backend_entity.process_type

    @field(readonly=True)
    def ctime(self) -> datetime.datetime:
        """The creation time of the node."""
        return self._backend_entity.ctime

    @field(readonly=True)
    def mtime(self) -> datetime.datetime:
        """The last modification time of the node."""
        return self._backend_entity.mtime

    @field(
        readonly=True,
        model_field_info=ModelFieldInfo(default_factory=dict),
    )
    def repository_metadata(self) -> dict[str, t.Any]:
        """The repository metadata of the node."""
        return self.base.repository.metadata

    @functools.cached_property
    def base(self) -> NodeBase:
        """Return the base of the node."""
        return NodeBase(self)  # type: ignore[arg-type]

    @classproperty
    def class_node_type(cls: type[Node]) -> str:  # noqa: N805
        return cls._plugin_type_string

    @classproperty
    def _plugin_type_string(cls: type[Node]) -> str:  # noqa: N805
        if not hasattr(cls, '__plugin_type_string'):
            cls.__plugin_type_string = get_type_string_from_class(cls.__module__, cls.__name__)
        return cls.__plugin_type_string

    def _check_mutability_attributes(self, keys: list[str] | None = None) -> None:
        """Check if the entity is mutable and raise an exception if not.

        This is called from `NodeAttributes` methods that modify the attributes.

        :param keys: the keys that will be mutated, or all if None
        """
        if self.is_stored:
            raise exceptions.ModificationNotAllowed('the attributes of a stored entity are immutable')
