from __future__ import annotations

import typing as t

from entity import Entity
from fields import field

from aiida.common.lang import classproperty
from aiida.manage import get_manager
from aiida.orm import Computer, User
from aiida.orm.implementation import BackendNode, StorageBackend
from aiida.orm.utils.node import get_type_string_from_class


class Node(Entity[BackendNode]):
    __plugin_type_string: t.ClassVar[str]

    def __init__(
        self,
        label: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
        attributes: dict | None = None,
        repository_metadata: dict | None = None,
        files: dict | None = None,
        computer: Computer | None = None,
        user: User | None = None,
        backend: StorageBackend | None = None,
        **kwargs,
    ):
        backend = backend or get_manager().get_profile_storage()

        if computer and not computer.is_stored:
            raise ValueError('the computer is not stored')

        backend_computer = computer.backend_entity if computer else None
        user = user if user else backend.default_user

        if user is None:
            raise ValueError('the user cannot be None')

        backend_entity = backend.nodes.create(
            label=label,
            description=description,
            extras=extras,
            attributes=attributes,
            repository_metadata=repository_metadata,
            node_type=self.class_node_type,
            user=user.backend_entity,
            computer=backend_computer,
            **kwargs,
        )

        super().__init__(backend_entity, **kwargs)

        if files:
            # TODO: Implement the logic to handle files associated with the node.
            pass

    @field
    def label(self) -> str:
        """The label of the node."""
        return self._backend_entity.label

    @label.setter
    def label(self, value: str):
        self._backend_entity.label = value

    @field
    def description(self) -> str:
        """The description of the node."""
        return self._backend_entity.description

    @description.setter
    def description(self, value: str):
        self._backend_entity.description = value

    @field
    def extras(self) -> dict:
        """The extras of the node."""
        return self._backend_entity.extras

    @extras.setter
    def extras(self, value: dict):
        self._backend_entity.extras = value

    @field
    def attributes(self) -> dict:
        """The attributes of the node."""
        return self._backend_entity.attributes

    @field
    def repository_metadata(self) -> dict:
        """The repository metadata of the node."""
        return self._backend_entity.repository_metadata

    @field
    def user(self) -> User:
        """The user associated with the node."""
        return Entity.from_backend_entity(User, self._backend_entity.user)

    @field
    def computer(self) -> Computer | None:
        """The computer associated with the node."""
        return Entity.from_backend_entity(Computer, self._backend_entity.computer)

    @field(readonly=True)
    def uuid(self) -> str:
        """The UUID of the node."""
        return self._backend_entity.uuid

    @field(readonly=True)
    def node_type(self) -> str:
        """The type of the node."""
        return self._backend_entity.node_type

    @field(readonly=True)
    def ctime(self) -> str:
        """The creation time of the node."""
        return self._backend_entity.ctime

    @field(readonly=True)
    def mtime(self) -> str:
        """The last modification time of the node."""
        return self._backend_entity.mtime

    @classproperty
    def class_node_type(cls) -> str:  # noqa: N805
        return cls._plugin_type_string

    @classproperty
    def _plugin_type_string(cls) -> str:  # noqa: N805
        if not hasattr(cls, '__plugin_type_string'):
            cls.__plugin_type_string = get_type_string_from_class(cls.__module__, cls.__name__)
        return cls.__plugin_type_string
