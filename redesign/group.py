from __future__ import annotations

import datetime
import functools
import typing as t

from adapters import EntityPkAdapter
from entity import Entity
from fields import field
from user import User

from aiida.common.lang import classproperty
from aiida.manage.manager import get_manager
from aiida.orm.groups import GroupBase
from aiida.orm.implementation import BackendGroup, StorageBackend


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

        model = backend.groups.create(
            label=label, user=user.backend_entity, description=description, type_string=self._type_string, time=time
        )
        super().__init__(model)

        self._base = GroupBase(self)

        if extras is not None:
            self._base.extras.set_many(extras)

    @field
    def label(self) -> str:
        """The label of the group."""
        return self._backend_entity.label

    @field
    def description(self) -> str:
        """The description of the group."""
        return self._backend_entity.description

    @description.setter
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @field
    def time(self) -> datetime.datetime:
        """The time of the group."""
        return self._backend_entity.time

    @field(model_adapter=EntityPkAdapter(User))
    def user(self) -> User:
        """The user of the group."""
        return User(self._backend_entity.user)

    @field
    def extras(self) -> dict[str, t.Any]:
        """The extras of the group."""
        return self.base.extras.all

    @extras.setter
    def extras(self, value: dict[str, t.Any]) -> None:
        self.base.extras.reset(value)

    @functools.cached_property
    def base(self) -> GroupBase:
        """Return the base of the group."""
        return self._base

    @classproperty
    def _type_string(cls) -> str | None:  # noqa: N805
        from aiida.plugins.entry_point import get_entry_point_from_class

        if hasattr(cls, '__type_string'):
            return cls.__type_string

        mod, name = cls.__module__, cls.__name__
        entry_point_group, entry_point = get_entry_point_from_class(mod, name)

        if entry_point_group is None or entry_point_group != 'aiida.groups':
            cls.__type_string = None  # type: ignore[misc]
        else:
            assert entry_point is not None
            cls.__type_string = entry_point.name  # type: ignore[misc]
        return cls.__type_string
