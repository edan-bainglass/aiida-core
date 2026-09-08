from __future__ import annotations

import typing as t

import pydantic as pdt

from aiida import orm
from aiida.common import exceptions
from aiida.manage.manager import get_manager
from aiida.new_orm.columns import column
from aiida.new_orm.entity import Entity
from aiida.orm.implementation import BackendComputer

if t.TYPE_CHECKING:
    from aiida.orm.implementation import StorageBackend

__all__ = ('Computer',)


class Computer(Entity[BackendComputer]):
    """ORM representation of an AiiDA computer."""

    def __init__(
        self,
        label: str,
        hostname: str,
        transport_type: str,
        scheduler_type: str,
        description: str = '',
        metadata: dict[str, t.Any] | None = None,
        backend: StorageBackend | None = None,
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
        super().__init__(backend_entity)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self!s}>'

    def __str__(self) -> str:
        return f'{self.label} ({self.hostname}), pk: {self.pk}'

    @column(updatable=True)
    def label(self) -> str:
        """The label of the computer."""
        return self._backend_entity.label

    @label.setter
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @column
    def hostname(self) -> str:
        """The hostname of the computer."""
        return self._backend_entity.hostname

    @hostname.setter
    def hostname(self, value: str) -> None:
        self._backend_entity.hostname = value

    @column
    def transport_type(self) -> str:
        """The transport type of the computer."""
        return self._backend_entity.get_transport_type()

    @transport_type.setter
    def transport_type(self, value: str) -> None:
        self._backend_entity.set_transport_type(value)

    @column
    def scheduler_type(self) -> str:
        """The scheduler type of the computer."""
        return self._backend_entity.get_scheduler_type()

    @scheduler_type.setter
    def scheduler_type(self, value: str) -> None:
        self._backend_entity.set_scheduler_type(value)

    @column(
        updatable=True,
        model_field_info=pdt.fields.FieldInfo(default=''),
    )
    def description(self) -> str:
        """The description of the computer."""
        return self._backend_entity.description

    @description.setter
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @column(
        may_be_large=True,
        model_field_info=pdt.fields.FieldInfo(default_factory=dict),
    )
    def metadata(self) -> dict[str, t.Any]:
        """The metadata of the computer."""
        return self._backend_entity.get_metadata()

    @metadata.setter
    def metadata(self, value: dict[str, t.Any]) -> None:
        self._backend_entity.set_metadata(value)

    @column(readonly=True)
    def uuid(self) -> str:
        """The UUID of the computer."""
        return self._backend_entity.uuid

    @classmethod
    def get_one(cls, identifier: int | str) -> Computer:
        """Get a computer by identifier (PK or label)."""
        try:
            return orm.load_computer(identifier)  # type: ignore[return-value]
        except exceptions.NotExistent:
            raise ValueError(f'Computer with identifier {identifier} does not exist') from None
