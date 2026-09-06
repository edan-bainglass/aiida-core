from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable

from typing_extensions import Self

from aiida.common import exceptions
from aiida.orm import fields as qb_fields

from .cli_adapter import CliAdapter
from .fields import (
    BaseField,
    BaseFieldConfig,
    BaseFieldDecorator,
    BaseFieldSpec,
    CliFieldInfo,
    ModelFieldInfo,
    Storable,
)
from .model_adapter import ModelAdapter

__all__ = (
    'Column',
    'ColumnConfig',
    'ColumnSpec',
    'column',
    'iter_columns',
)


@dataclasses.dataclass(frozen=True)
class ColumnSpec(BaseFieldSpec):
    """Canonical semantic description of a top-level entity column."""

    backend_key: str
    updatable: bool
    may_be_large: bool = False

    @property
    def immutable(self) -> bool:
        """Return whether the column is immutable after storage."""
        return not self.updatable


@dataclasses.dataclass(frozen=True)
class ColumnConfig(BaseFieldConfig):
    """Unresolved configuration supplied to the `column` decorator."""

    backend_key: str | None = None
    updatable: bool = False
    may_be_large: bool = False


_EntityT = t.TypeVar('_EntityT', bound=Storable)
_ValueT = t.TypeVar('_ValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)


class Column(
    BaseField[
        _EntityT,
        _ValueT,
        _QbFieldT,
        ColumnSpec,
        ColumnConfig,
    ],
):
    """Descriptor declaring a top-level ORM entity column."""

    config_type = ColumnConfig
    spec_type = ColumnSpec

    def __init__(
        self,
        fget: Callable[[_EntityT], _ValueT],
        fset: Callable[[_EntityT, _ValueT], None] | None = None,
        fdel: Callable[[_EntityT], None] | None = None,
        *,
        config: ColumnConfig | None = None,
    ) -> None:
        super().__init__(fget, fset, fdel, config=config or ColumnConfig())
        self._qb_field: _QbFieldT | None = None

    @t.overload
    def __get__(self, instance: None, owner: type[_EntityT]) -> _QbFieldT: ...

    @t.overload
    def __get__(self, instance: _EntityT, owner: type[_EntityT] | None = None) -> _ValueT: ...

    def __get__(
        self,
        instance: _EntityT | None,
        owner: type[_EntityT] | None = None,
    ) -> _ValueT | _QbFieldT:
        if instance is None:
            if owner is None:
                raise AttributeError('ORM column must be accessed through an entity class')

            return self._get_qb_field(owner)

        return self.fget(instance)

    def __set__(self, instance: _EntityT, value: _ValueT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('column has not been assigned to an entity')

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.fset is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no setter')

        if instance.is_stored and self.spec.immutable:
            raise exceptions.ModificationNotAllowed(f'{self._owner.__name__}.{self._name} is immutable once stored')

        self.fset(instance, value)

    def __delete__(self, instance: _EntityT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('column has not been assigned to an entity')

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.fdel is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no deleter')

        if instance.is_stored and self.spec.immutable:
            raise exceptions.ModificationNotAllowed(
                f'{self._owner.__name__}.{self._name} cannot be deleted after storing'
            )

        self.fdel(instance)

    def getter(self, fget: Callable[[_EntityT], _ValueT], /) -> Self:
        """Set the getter and return this descriptor."""
        super().getter(fget)
        self._qb_field = None
        return self

    def setter(self, fset: Callable[[_EntityT, _ValueT], None], /) -> Self:
        """Set the setter and return this descriptor."""
        if self._config.readonly:
            raise TypeError('cannot define a setter for a read-only ORM column')

        self.fset = fset
        self._spec = None
        return self

    def deleter(self, fdel: Callable[[_EntityT], None], /) -> Self:
        """Set the deleter and return this descriptor."""
        if self._config.readonly:
            raise TypeError('cannot define a deleter for a read-only ORM column')

        self.fdel = fdel
        return self

    def _build_qb_field(self) -> _QbFieldT:
        """Build the QueryBuilder field."""
        spec = self.spec

        return t.cast(
            _QbFieldT,
            qb_fields.add_field(
                spec.backend_key,
                dtype=self.adapted_type,
                doc=spec.description,
                is_attribute=False,
            ),
        )

    def _get_qb_field(self, owner: type[_EntityT]) -> _QbFieldT:
        """Return the lazily generated QueryBuilder field."""
        if self._qb_field is None:
            self._qb_field = self._build_qb_field()

        return self._qb_field

    def _build_spec(self, **kwargs: t.Any) -> ColumnSpec:
        """Resolve descriptor structure into the canonical column specification."""
        if self._name is None:
            raise RuntimeError('column has not been assigned to an entity')

        if self._config.readonly and self._config.updatable:
            raise TypeError(f'{self._name!r} cannot be both read-only and updatable')

        if self._config.readonly and self.fset is not None:
            raise TypeError(f'{self._name!r} is declared read-only but defines a setter')

        if self._config.updatable and self.fset is None:
            raise TypeError(f'{self._name!r} is declared updatable but defines no setter')

        return super()._build_spec(
            backend_key=self._config.backend_key or self._name,
            updatable=self._config.updatable,
            may_be_large=self._config.may_be_large,
        )


_ConfiguredQbFieldT = t.TypeVar('_ConfiguredQbFieldT', bound=qb_fields.QbField)


class ConfiguredColumnDecorator(t.Protocol[_ConfiguredQbFieldT]):
    """Configured column decorator with a known QueryBuilder field type."""

    def __call__(
        self,
        fget: Callable[[_EntityT], _ValueT],
        /,
    ) -> Column[_EntityT, _ValueT, _ConfiguredQbFieldT]: ...


_AdaptedEntityT = t.TypeVar('_AdaptedEntityT')
_AdaptedModelT = t.TypeVar('_AdaptedModelT')


class ColumnDecorator(
    BaseFieldDecorator[
        _EntityT,
        _ValueT,
        ColumnConfig,
        Column[t.Any, t.Any, qb_fields.QbField],
    ],
):
    """Decorator for top-level entity columns."""

    config_type = ColumnConfig
    field_type = Column

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], int],
        /,
    ) -> Column[_EntityT, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], int | None],
        /,
    ) -> Column[_EntityT, int | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], float],
        /,
    ) -> Column[_EntityT, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], float | None],
        /,
    ) -> Column[_EntityT, float | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], datetime.datetime],
        /,
    ) -> Column[_EntityT, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], datetime.datetime | None],
        /,
    ) -> Column[_EntityT, datetime.datetime | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], str],
        /,
    ) -> Column[_EntityT, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], str | None],
        /,
    ) -> Column[_EntityT, str | None, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], list[_ValueT]],
        /,
    ) -> Column[_EntityT, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], list[_ValueT] | None],
        /,
    ) -> Column[_EntityT, list[_ValueT] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], tuple[_ValueT, ...]],
        /,
    ) -> Column[_EntityT, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], tuple[_ValueT, ...] | None],
        /,
    ) -> Column[_EntityT, tuple[_ValueT, ...] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], dict[str, _ValueT]],
        /,
    ) -> Column[_EntityT, dict[str, _ValueT], qb_fields.QbDictField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_EntityT], dict[str, _ValueT] | None],
        /,
    ) -> Column[_EntityT, dict[str, _ValueT] | None, qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_EntityT], object],
        /,
    ) -> Column[_EntityT, object, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-cannot-match]
        self,
        fget: Callable[[_EntityT], _ValueT],
        /,
    ) -> Column[_EntityT, _ValueT, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        *,
        backend_key: str | None = None,
        readonly: bool = False,
        updatable: bool = False,
        required_once_stored: bool = False,
        may_be_large: bool = False,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: ModelAdapter[_AdaptedEntityT, _AdaptedModelT, _QbFieldT],
        cli_field_info: CliFieldInfo | None = None,
        cli_adapter: CliAdapter[t.Any, t.Any] | None = None,
    ) -> ConfiguredColumnDecorator[_QbFieldT]: ...

    @t.overload
    def __call__(
        self,
        *,
        backend_key: str | None = None,
        readonly: bool = False,
        updatable: bool = False,
        required_once_stored: bool = False,
        may_be_large: bool = False,
        model_field_info: ModelFieldInfo | None = None,
        model_adapter: None = None,
        cli_field_info: CliFieldInfo | None = None,
        cli_adapter: CliAdapter[t.Any, t.Any] | None = None,
    ) -> Self: ...

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return self._call(*args, **kwargs)


column: ColumnDecorator = ColumnDecorator()


def iter_columns(entity: type) -> dict[str, Column]:
    """Return all effective ORM columns on an entity hierarchy."""
    result: dict[str, Column] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, Column):
                result[name] = value
            elif name in result:
                del result[name]

    return result
