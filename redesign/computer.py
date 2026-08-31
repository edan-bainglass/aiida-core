from __future__ import annotations

import typing as t

from entity import Entity
from fields import ModelFieldInfo, field

from aiida import orm
from aiida.manage.manager import get_manager
from aiida.orm.implementation import BackendComputer, StorageBackend


class Computer(Entity[BackendComputer]):
    def __init__(
        self,
        label: str,
        hostname: str,
        transport_type: str,
        scheduler_type: str,
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

    @field(updatable=True)
    def label(self) -> str:
        """The label of the computer."""
        return self._backend_entity.label

    @label.setter  # type: ignore[no-redef]
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @field
    def hostname(self) -> str:
        """The hostname of the computer."""
        return self._backend_entity.hostname

    @hostname.setter  # type: ignore[no-redef]
    def hostname(self, value: str) -> None:
        self._backend_entity.hostname = value

    @field
    def transport_type(self) -> str:
        """The transport type of the computer."""
        return self._backend_entity.get_transport_type()

    @transport_type.setter  # type: ignore[no-redef]
    def transport_type(self, value: str) -> None:
        self._backend_entity.set_transport_type(value)

    @field
    def scheduler_type(self) -> str:
        """The scheduler type of the computer."""
        return self._backend_entity.get_scheduler_type()

    @scheduler_type.setter  # type: ignore[no-redef]
    def scheduler_type(self, value: str) -> None:
        self._backend_entity.set_scheduler_type(value)

    @field(
        updatable=True,
        model_field_info=ModelFieldInfo(default=''),
    )
    def description(self) -> str:
        """The description of the computer."""
        return self._backend_entity.description

    @description.setter  # type: ignore[no-redef]
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @field(model_field_info=ModelFieldInfo(default_factory=dict))
    def metadata(self) -> dict[str, t.Any]:
        """The metadata of the computer."""
        return self._backend_entity.get_metadata()

    @metadata.setter  # type: ignore[no-redef]
    def metadata(self, value: dict[str, t.Any]) -> None:
        self._backend_entity.set_metadata(value)

    @classmethod
    def get_one(cls, pk: int) -> Computer | None:
        """Get a computer by primary key."""
        return orm.Computer.collection.get(pk=pk)  # type: ignore[return-value]
