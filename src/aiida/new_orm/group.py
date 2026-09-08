from __future__ import annotations

import datetime
import functools
import typing as t

from typing_extensions import Self

from aiida import orm
from aiida.common import exceptions
from aiida.common.lang import classproperty
from aiida.manage.manager import get_manager
from aiida.new_orm.adapters import EntityPkAdapter, StrUuidAdapter
from aiida.new_orm.columns import column
from aiida.new_orm.entity import Entity, from_backend_entity
from aiida.new_orm.fields import ModelFieldInfo
from aiida.new_orm.user import User
from aiida.orm import groups
from aiida.orm.implementation import BackendGroup, StorageBackend

__all__ = ('Group',)


class Group(Entity[BackendGroup]):
    """ORM representation of an AiiDA group."""

    __type_string: t.ClassVar[str | None]

    def __init__(
        self,
        label: str,
        user: User | None = None,
        description: str = '',
        time: datetime.datetime | None = None,
        extras: dict[str, t.Any] | None = None,
        backend: StorageBackend | None = None,
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

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__}: {self.label!r} '
            f'[{"type " + self.type_string if self.type_string else "user-defined"}], of user {self.user.email}>'
        )

    def __str__(self) -> str:
        return f'{self.__class__.__name__}<{self.label}>'

    @column(updatable=True)
    def label(self) -> str:
        """The label of the group."""
        return self._backend_entity.label

    @label.setter
    def label(self, value: str) -> None:
        self._backend_entity.label = value

    @column(updatable=True)
    def description(self) -> str:
        """The description of the group."""
        return self._backend_entity.description

    @description.setter
    def description(self, value: str) -> None:
        self._backend_entity.description = value

    @column(
        readonly=True,
        model_adapter=StrUuidAdapter(),
    )
    def uuid(self) -> str:
        """The UUID of the group."""
        return self._backend_entity.uuid

    @column(readonly=True)
    def time(self) -> datetime.datetime:
        """The time of the group."""
        return self._backend_entity.time

    @column(
        readonly=True,
        model_adapter=EntityPkAdapter(User),
    )
    def user(self) -> User:
        """The user of the group."""
        return from_backend_entity(User, self._backend_entity.user)

    @column(
        updatable=True,
        may_be_large=True,
        model_field_info=ModelFieldInfo(default_factory=dict),
    )
    def extras(self) -> dict[str, t.Any]:
        """The extras of the group."""
        return self.base.extras.all

    @extras.setter
    def extras(self, value: dict[str, t.Any]) -> None:
        self.base.extras.reset(value)

    @functools.cached_property
    def base(self) -> groups.GroupBase:
        """Return the base of the group."""
        return self._base

    @property
    def type_string(self) -> str:
        """:return: the string defining the type of the group"""
        return self._backend_entity.type_string

    def store(self) -> Self:
        """Verify that the group is allowed to be stored, which is the case along as `type_string` is set."""
        if self._type_string is None:
            raise exceptions.StoringNotAllowed('`type_string` is `None` so the group cannot be stored.')

        return super().store()

    @classmethod
    def get_one(cls, identifier: int | str) -> Group:
        """Get a group by identifier (PK or label)."""
        try:
            return orm.load_group(identifier)  # type: ignore[return-value]
        except exceptions.NotExistent:
            raise ValueError(f'Group with identifier {identifier} does not exist') from None

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
