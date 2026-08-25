from __future__ import annotations

import abc
import dataclasses
import datetime
import enum
import typing as t
from collections.abc import Callable

from pydantic import Field as ModelField
from pydantic.fields import FieldInfo as ModelFieldInfo

from aiida.orm import fields as qb_fields

if t.TYPE_CHECKING:
    from entity import Entity


__all__ = (
    'CliFieldInfo',
    'FieldAccess',
    'FieldSpec',
    'ModelAdapter',
    'ModelField',
    'ModelFieldInfo',
    'OrmField',
    'field',
    'iter_fields',
)


_OwnerT = t.TypeVar('_OwnerT', bound='Entity')
_ValueT = t.TypeVar('_ValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)

_OrmValueT = t.TypeVar('_OrmValueT')
_ModelValueT = t.TypeVar('_ModelValueT')


class FieldAccess(enum.Enum):
    """Access semantics of an ORM field."""

    READ_ONLY = 'read_only'
    CREATE_ONLY = 'create_only'
    MUTABLE = 'mutable'


@dataclasses.dataclass(frozen=True)
class FieldSpec:
    """Canonical semantic description of an ORM field."""

    name: str
    value_type: t.Any
    backend_key: str
    access: FieldAccess
    description: str

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


class ModelAdapter(t.Generic[_OrmValueT, _ModelValueT], abc.ABC):
    """Adapt a field value between its ORM and model representations."""

    model_type: t.ClassVar[t.Any]

    @abc.abstractmethod
    def to_model(self, value: _OrmValueT) -> _ModelValueT:
        """Convert an ORM value to its model representation."""

    @abc.abstractmethod
    def to_orm(self, value: _ModelValueT) -> _OrmValueT:
        """Convert a model value to its ORM representation."""


@dataclasses.dataclass(frozen=True)
class CliFieldInfo:
    """Optional Click-specific configuration for an ORM field.

    Validation, defaults and constraints are expected to come from the
    generated Pydantic model. This class contains only CLI-specific
    interaction and presentation settings.
    """

    option: str | tuple[str, ...] | None = None
    metavar: str | None = None
    help: str | None = None
    prompt: bool | str | None = None
    hidden: bool = False


@dataclasses.dataclass(frozen=True)
class _FieldConfig:
    """Unresolved configuration supplied to the `field` decorator."""

    # ORM
    backend_key: str | None = None
    readonly: bool = False

    # Model
    model_field_info: ModelFieldInfo | None = None
    model_adapter: ModelAdapter[t.Any, t.Any] | None = None

    # CLI
    cli_field_info: CliFieldInfo | None = None


class OrmField(property, t.Generic[_OwnerT, _ValueT, _QbFieldT]):
    """Descriptor implementing an ORM field."""

    def __init__(
        self,
        fget: Callable[[_OwnerT], _ValueT] | None = None,
        fset: Callable[[_OwnerT, _ValueT], None] | None = None,
        fdel: Callable[[_OwnerT], None] | None = None,
        doc: str | None = None,
        *,
        config: _FieldConfig | None = None,
    ) -> None:
        super().__init__(fget, fset, fdel, doc)

        self._owner: type[_OwnerT] | None = None
        self._name: str | None = None
        self._config = config or _FieldConfig()

        self._spec: FieldSpec | None = None
        self._qb_field: _QbFieldT | None = None

    def __set_name__(self, owner: type[_OwnerT], name: str) -> None:
        self._owner = owner
        self._name = name

    @property
    def spec(self) -> FieldSpec:
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

    @property
    def qb_field(self) -> _QbFieldT:
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
    def __get__(
        self,
        instance: None,
        owner: type[_OwnerT],
    ) -> _QbFieldT: ...

    @t.overload
    def __get__(
        self,
        instance: _OwnerT,
        owner: type[_OwnerT] | None = None,
    ) -> _ValueT: ...

    def __get__(
        self,
        instance: _OwnerT | None,
        owner: type[_OwnerT] | None = None,
    ) -> _ValueT | _QbFieldT:
        if instance is None:
            return self.qb_field

        return t.cast(_ValueT, super().__get__(instance, owner))

    def __set__(self, instance: _OwnerT, value: _ValueT) -> None:
        assert self._owner is not None
        assert self._name is not None

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.spec.immutable:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is immutable')

        super().__set__(instance, value)

    def getter(
        self,
        fget: Callable[[_OwnerT], _ValueT],
        /,
    ) -> OrmField[_OwnerT, _ValueT, _QbFieldT]:
        """Return a copy with a different getter."""
        result = t.cast(
            OrmField[_OwnerT, _ValueT, _QbFieldT],
            super().getter(fget),
        )
        result._config = self._config
        return result

    def setter(
        self,
        fset: Callable[[_OwnerT, _ValueT], None],
        /,
    ) -> OrmField[_OwnerT, _ValueT, _QbFieldT]:
        """Return a copy with a different setter."""
        if self._config.readonly:
            raise TypeError('cannot define a setter for a read-only ORM field')

        result = t.cast(
            OrmField[_OwnerT, _ValueT, _QbFieldT],
            super().setter(fset),
        )
        result._config = self._config
        return result

    def deleter(
        self,
        fdel: Callable[[_OwnerT], None],
        /,
    ) -> OrmField[_OwnerT, _ValueT, _QbFieldT]:
        """Return a copy with a different deleter."""
        result = t.cast(
            OrmField[_OwnerT, _ValueT, _QbFieldT],
            super().deleter(fdel),
        )
        result._config = self._config
        return result

    def _build_spec(self) -> FieldSpec:
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

        return FieldSpec(
            name=self._name,
            value_type=value_type,
            backend_key=self._config.backend_key or self._name,
            access=access,
            description=(self.__doc__ or '').strip(),
        )


class OrmFieldDecorator:
    """Decorator factory for ORM fields."""

    def __init__(self, config: _FieldConfig | None = None) -> None:
        self._config = config or _FieldConfig()

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
    ) -> OrmField[
        _OwnerT,
        datetime.datetime,
        qb_fields.QbNumericField,
    ]: ...

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
    ) -> OrmField[
        _OwnerT,
        list[_ValueT],
        qb_fields.QbArrayField,
    ]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], tuple[_ValueT, ...]],
        /,
    ) -> OrmField[
        _OwnerT,
        tuple[_ValueT, ...],
        qb_fields.QbArrayField,
    ]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], dict[str, _ValueT]],
        /,
    ) -> OrmField[
        _OwnerT,
        dict[str, _ValueT],
        qb_fields.QbDictField,
    ]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], _ValueT],
        /,
    ) -> OrmField[
        _OwnerT,
        _ValueT,
        qb_fields.QbAnyField,
    ]: ...

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
            return type(self)(_FieldConfig(**kwargs))

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
