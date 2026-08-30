from __future__ import annotations

import typing as t

from entity import Entity
from fields import ModelField, field

from aiida.manage.manager import get_manager
from aiida.orm.implementation import BackendComputer, StorageBackend


class Computer(Entity[BackendComputer]):
    def __init__(
        self,
        hostname: str,
        transport_type: str,
        scheduler_type: str,
        label: str | None = None,
        description: str = '',
        metadata: dict[str, t.Any] | None = None,
        backend: StorageBackend | None = None,
        **kwargs,
    ):
        backend = backend or get_manager().get_profile_storage()
        backend_entity = backend.computers.create(
            hostname=hostname,
            transport_type=transport_type,
            scheduler_type=scheduler_type,
            label=label,
            description=description,
            metadata=metadata,
        )
        super().__init__(backend_entity, **kwargs)

    @field(
        updatable=True,
        model_field_info=ModelField(''),
    )
    def description(self) -> str:
        """The description of the computer."""
        return self._backend_entity.description

    @description.setter
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @field
    def label(self) -> str:
        """The label of the computer."""
        return self._backend_entity.label

    @label.setter
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @field
    def hostname(self) -> str:
        """The hostname of the computer."""
        return self._backend_entity.hostname

    @hostname.setter
    def hostname(self, value: str) -> None:
        self._backend_entity.hostname = value

    @field
    def transport_type(self) -> str:
        """The transport type of the computer."""
        return self._backend_entity.get_transport_type()

    @transport_type.setter
    def transport_type(self, value: str) -> None:
        self._backend_entity.set_transport_type(value)

    @field
    def scheduler_type(self) -> str:
        """The scheduler type of the computer."""
        return self._backend_entity.get_scheduler_type()

    @scheduler_type.setter
    def scheduler_type(self, value: str) -> None:
        self._backend_entity.set_scheduler_type(value)

    @field(model_field_info=ModelField(default_factory=dict))
    def metadata(self) -> dict[str, t.Any]:
        """The metadata of the computer."""
        return self._backend_entity.get_metadata()

    @metadata.setter
    def metadata(self, value: dict[str, t.Any]) -> None:
        self._backend_entity.set_metadata(value)

    @staticmethod
    def get_one(pk: int) -> Computer | None:
        """Get a computer by primary key."""
        from aiida import orm

        return orm.Computer.collection.get(pk=pk)
