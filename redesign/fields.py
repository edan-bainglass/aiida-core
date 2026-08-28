from __future__ import annotations

import dataclasses
import datetime
import enum
import typing as t
from collections.abc import Callable

from pydantic import Field as ModelField
from pydantic.fields import FieldInfo as ModelFieldInfo
from typing_extensions import Self

from aiida.orm import fields as qb_fields

if t.TYPE_CHECKING:
    from entity import Entity
    from models import ModelAdapter


__all__ = (
    'CliFieldInfo',
    'EntityFieldSpec',
    'FieldAccess',
    'ModelField',
    'ModelFieldInfo',
    'OrmField',
    'field',
    'iter_fields',
)


_OwnerT = t.TypeVar('_OwnerT', bound='Entity')
_ValueT = t.TypeVar('_ValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)


class FieldAccess(enum.Enum):
    """Access semantics of an ORM field."""

    READ_ONLY = 'read_only'
    CREATE_ONLY = 'create_only'
    MUTABLE = 'mutable'


@dataclasses.dataclass(frozen=True)
class BaseFieldSpec:
    """Base class for field specifications."""

    name: str
    value_type: t.Any
    description: str


@dataclasses.dataclass(frozen=True)
class EntityFieldSpec(BaseFieldSpec):
    """Canonical semantic description of an ORM entity field."""

    backend_key: str
    access: FieldAccess

    @property
    def readonly(self) -> bool:
        """Return whether the field is read-only."""
        return self.access is FieldAccess.READ_ONLY

    @property
    def immutable(self) -> bool:
        """Return whether the field is immutable after creation."""
        return self.access is FieldAccess.CREATE_ONLY

    @property
    def mutable(self) -> bool:
        """Return whether the field is mutable."""
        return self.access is FieldAccess.MUTABLE


@dataclasses.dataclass(frozen=True)
class CliFieldInfo:
    """Optional Click-specific configuration for an ORM field.

    Validation, defaults and constraints are expected to come from the generated Pydantic model.
    This class contains only CLI-specific interaction and presentation settings.
    """

    option: str | tuple[str, ...] | None = None
    metavar: str | None = None
    help: str | None = None
    prompt: bool | str | None = None
    hidden: bool = False


@dataclasses.dataclass(frozen=True)
class BaseFieldConfig:
    """Base class for field configuration."""

    model_field_info: ModelFieldInfo | None = None
    model_adapter: ModelAdapter[t.Any, t.Any] | None = None


@dataclasses.dataclass(frozen=True)
class FieldConfig(BaseFieldConfig):
    """Unresolved configuration supplied to the `field` decorator."""

    backend_key: str | None = None
    readonly: bool = False

    cli_field_info: CliFieldInfo | None = None


class OrmField(t.Generic[_OwnerT, _ValueT, _QbFieldT]):
    """Descriptor implementing an ORM field."""

    def __init__(
        self,
        fget: Callable[[_OwnerT], _ValueT] | None = None,
        fset: Callable[[_OwnerT, _ValueT], None] | None = None,
        fdel: Callable[[_OwnerT], None] | None = None,
        doc: str | None = None,
        *,
        config: FieldConfig | None = None,
    ) -> None:
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc if doc is not None else getattr(fget, '__doc__', None)

        self._owner: type[_OwnerT] | None = None
        self._name: str | None = None
        self._config = config or FieldConfig()

        self._spec: EntityFieldSpec | None = None
        self._qb_field: _QbFieldT | None = None

    def __set_name__(self, owner: type[_OwnerT], name: str) -> None:
        self._owner = owner
        self._name = name

    @property
    def spec(self) -> EntityFieldSpec:
        """Return the lazily resolved field specification."""
        if self._spec is None:
            self._spec = self._build_spec()

        return self._spec

    @property
    def model_field_info(self) -> ModelFieldInfo | None:
        """Return optional Pydantic-specific field configuration."""
        return self._config.model_field_info

    @property
    def model_adapter(self) -> ModelAdapter[t.Any, t.Any] | None:
        """Return the ORM/model value adapter."""
        return self._config.model_adapter

    @property
    def cli_field_info(self) -> CliFieldInfo | None:
        """Return optional CLI-specific field configuration."""
        return self._config.cli_field_info

    def _get_qb_field(self, owner: type[_OwnerT]) -> _QbFieldT:
        """Return the lazily generated QueryBuilder field."""
        if self._qb_field is None:
            spec = self.spec
            self._qb_field = t.cast(
                _QbFieldT,
                qb_fields.add_field(
                    spec.backend_key,
                    dtype=spec.value_type,
                    doc=spec.description,
                    is_attribute=False,
                ),
            )

        return self._qb_field

    @t.overload
    def __get__(self, instance: None, owner: type[_OwnerT]) -> _QbFieldT: ...

    @t.overload
    def __get__(self, instance: _OwnerT, owner: type[_OwnerT] | None = None) -> _ValueT: ...

    def __get__(
        self,
        instance: _OwnerT | None,
        owner: type[_OwnerT] | None = None,
    ) -> _ValueT | _QbFieldT:
        if instance is None:
            if owner is None:
                raise AttributeError('ORM field must be accessed through an entity class')

            return self._get_qb_field(owner)

        if self.fget is None:
            raise AttributeError(f"'{self.spec.name}' is not readable")

        return self.fget(instance)

    def __set__(self, instance: _OwnerT, value: _ValueT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('field has not been assigned to an entity')

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.spec.immutable:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is immutable')

        if self.fset is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no setter')

        self.fset(instance, value)

    def __delete__(self, instance: _OwnerT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('field has not been assigned to an entity')

        if self.fdel is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no deleter')

        self.fdel(instance)

    def getter(self, fget: Callable[[_OwnerT], _ValueT], /) -> Self:
        """Set the getter and return this descriptor."""
        self.fget = fget
        self.__doc__ = getattr(fget, '__doc__', None)

        self._spec = None
        self._qb_field = None

        return self

    def setter(self, fset: Callable[[_OwnerT, _ValueT], None], /) -> Self:
        """Set the setter and return this descriptor."""
        if self._config.readonly:
            raise TypeError('cannot define a setter for a read-only ORM field')

        self.fset = fset

        # Setter existence determines CREATE_ONLY versus MUTABLE.
        self._spec = None

        return self

    def deleter(self, fdel: Callable[[_OwnerT], None], /) -> Self:
        """Set the deleter and return this descriptor."""
        self.fdel = fdel
        return self

    def _build_spec(self) -> EntityFieldSpec:
        """Resolve descriptor structure into the canonical `FieldSpec`."""
        if self._name is None:
            raise RuntimeError('field has not been assigned to an entity')

        if self.fget is None:
            raise TypeError(f'{self._name} has no getter')

        if self._config.readonly and self.fset is not None:
            raise TypeError(f'{self._name!r} is declared read-only but defines a setter')

        value_type = t.get_type_hints(self.fget).get('return', t.Any)

        if self._config.readonly:
            access = FieldAccess.READ_ONLY
        elif self.fset is None:
            access = FieldAccess.CREATE_ONLY
        else:
            access = FieldAccess.MUTABLE

        return EntityFieldSpec(
            name=self._name,
            value_type=value_type,
            backend_key=self._config.backend_key or self._name,
            access=access,
            description=(self.__doc__ or '').strip(),
        )


class OrmFieldDecorator:
    """Decorator factory for ORM fields."""

    def __init__(self, config: FieldConfig | None = None) -> None:
        self._config = config or FieldConfig()

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], int],
        /,
    ) -> OrmField[_OwnerT, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], float],
        /,
    ) -> OrmField[_OwnerT, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], datetime.datetime],
        /,
    ) -> OrmField[_OwnerT, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], str],
        /,
    ) -> OrmField[_OwnerT, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], list[_ValueT]],
        /,
    ) -> OrmField[_OwnerT, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], tuple[_ValueT, ...]],
        /,
    ) -> OrmField[_OwnerT, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], dict[str, _ValueT]],
        /,
    ) -> OrmField[_OwnerT, dict[str, _ValueT], qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], _ValueT],
        /,
    ) -> OrmField[_OwnerT, _ValueT, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        *,
        backend_key: str | None = None,
        readonly: bool = False,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[t.Any, t.Any] | None = None,
        cli_field_info: CliFieldInfo | None = None,
    ) -> t.Self: ...

    def __call__(
        self,
        fget: Callable[[_OwnerT], _ValueT] | None = None,
        /,
        **kwargs: t.Any,
    ) -> t.Any:
        if fget is None:
            return type(self)(FieldConfig(**kwargs))

        return OrmField(fget, config=self._config)


field = OrmFieldDecorator()


def iter_fields(entity: type) -> dict[str, OrmField]:
    """Return all effective ORM fields on an entity hierarchy."""
    result: dict[str, OrmField] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, OrmField):
                result[name] = value
            elif name in result:
                del result[name]

    return result
