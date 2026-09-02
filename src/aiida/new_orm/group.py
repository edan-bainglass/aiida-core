from __future__ import annotations

import datetime
import functools
import typing as t

from aiida import orm
from aiida.common import exceptions
from aiida.common.lang import classproperty
from aiida.manage.manager import get_manager
from aiida.orm import groups
from aiida.orm.implementation import BackendGroup, StorageBackend

from .adapters import EntityPkAdapter, StrUuidAdapter
from .entity import Entity, from_backend_entity
from .fields import ModelFieldInfo, field
from .user import User


class Group(Entity[BackendGroup]):
    __type_string: t.ClassVar[str | None]

    def __init__(
        self,
        label: str,
        user: User | None = None,
        description: str = '',
        time: datetime.datetime | None = None,
        extras: dict[str, t.Any] | None = None,
        backend: StorageBackend | None = None,
        **kwargs,
    ):
        backend = backend or get_manager().get_profile_storage()
        user = t.cast(User, user or backend.default_user)

        backend_entity = backend.groups.create(
            label=label,
            user=user.backend_entity,
            description=description,
            type_string=self._type_string,
            time=time,
        )
        super().__init__(backend_entity)

        self._base = groups.GroupBase(self)  # type: ignore[arg-type]

        if extras is not None:
            self._base.extras.set_many(extras)

    @field(updatable=True)
    def label(self) -> str:
        """The label of the group."""
        return self._backend_entity.label

    @label.setter  # type: ignore[no-redef]
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @field(updatable=True)
    def description(self) -> str:
        """The description of the group."""
        return self._backend_entity.description

    @description.setter  # type: ignore[no-redef]
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @field(
        readonly=True,
        model_adapter=StrUuidAdapter(),
    )
    def uuid(self) -> str:
        """The UUID of the group."""
        return self._backend_entity.uuid

    @field(readonly=True)
    def time(self) -> datetime.datetime:
        """The time of the group."""
        return self._backend_entity.time

    @field(
        readonly=True,
        model_adapter=EntityPkAdapter(User),
    )
    def user(self) -> User:
        """The user of the group."""
        return from_backend_entity(User, self._backend_entity.user)

    @field(
        updatable=True,
        may_be_large=True,
        model_field_info=ModelFieldInfo(default_factory=dict),
    )
    def extras(self) -> dict[str, t.Any]:
        """The extras of the group."""
        return self.base.extras.all

    @extras.setter  # type: ignore[no-redef]
    def extras(self, value: dict[str, t.Any]) -> None:
        self.base.extras.reset(value)

    @functools.cached_property
    def base(self) -> groups.GroupBase:
        """Return the base of the group."""
        return self._base

    @classmethod
    def get_one(cls, identifier: int | str) -> Group | None:
        """Get a group by identifier (PK or label)."""
        try:
            return orm.load_group(identifier)  # type: ignore[return-value]
        except exceptions.NotExistent:
            return None

    @classproperty
    def _type_string(cls: type[Group]) -> str | None:  # noqa: N805
        from aiida.plugins.entry_point import get_entry_point_from_class

        if hasattr(cls, '__type_string'):
            return cls.__type_string

        mod, name = cls.__module__, cls.__name__
        entry_point_group, entry_point = get_entry_point_from_class(mod, name)

        if entry_point_group is None or entry_point_group != 'aiida.groups':
            cls.__type_string = None
        else:
            assert entry_point is not None
            cls.__type_string = entry_point.name
        return cls.__type_string
