from __future__ import annotations

import dataclasses
import datetime
import functools
import typing as t
from collections.abc import Callable

from pydantic.fields import FieldInfo as ModelFieldInfo
from typing_extensions import Self

from aiida.cmdline.params.options.interactive import TemplateInteractiveOption
from aiida.common import exceptions
from aiida.common.utils import is_nullable
from aiida.orm import fields as qb_fields

from .cli_adapter import CliAdapter
from .model_adapter import ModelAdapter

__all__ = (
    'CliFieldInfo',
    'EntityField',
    'EntityFieldSpec',
    'ModelFieldInfo',
    'field',
    'iter_fields',
)


@dataclasses.dataclass(frozen=True)
class BaseFieldSpec:
    """Base class for field specifications."""

    name: str
    value_type: t.Any
    description: str
    readonly: bool
    required_once_stored: bool


@dataclasses.dataclass(frozen=True)
class EntityFieldSpec(BaseFieldSpec):
    """Canonical semantic description of an ORM entity field."""

    backend_key: str
    updatable: bool
    may_be_large: bool = False

    @property
    def immutable(self) -> bool:
        """Return whether the field is immutable after creation."""
        return not self.updatable


@dataclasses.dataclass(frozen=True)
class CliFieldInfo:
    """Optional Click-specific configuration for an ORM field.

    Validation, defaults and constraints are expected to come from the generated Pydantic model.
    This class contains only CLI-specific interaction and presentation settings.
    """

    prompt: str | bool | None = None
    help: str = ''
    priority: int = 0
    short_name: str = ''
    option_cls: functools.partial[TemplateInteractiveOption] | None = None


@dataclasses.dataclass(frozen=True)
class BaseFieldConfig:
    """Base class for field configuration."""

    readonly: bool = False
    required_once_stored: bool = False
    model_field_info: ModelFieldInfo | None = None
    model_adapter: ModelAdapter[t.Any, t.Any, t.Any] | None = None
    cli_field_info: CliFieldInfo | None = None
    cli_adapter: CliAdapter[t.Any, t.Any] | None = None


@dataclasses.dataclass(frozen=True)
class EntityFieldConfig(BaseFieldConfig):
    """Unresolved configuration supplied to the `field` decorator."""

    backend_key: str | None = None
    updatable: bool = False
    may_be_large: bool = False


class Storable(t.Protocol):
    @property
    def is_stored(self) -> bool: ...


_OwnerT = t.TypeVar('_OwnerT', bound=Storable)
_ValueT = t.TypeVar('_ValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)
_SpecT = t.TypeVar('_SpecT', bound=BaseFieldSpec)
_ConfigT = t.TypeVar('_ConfigT', bound=BaseFieldConfig)


class BaseField(
    t.Generic[
        _OwnerT,
        _ValueT,
        _QbFieldT,
        _SpecT,
        _ConfigT,
    ]
):
    """Common infrastructure for typed ORM field declarations."""

    config_type: t.ClassVar[type[_ConfigT]]
    spec_type: t.ClassVar[type[_SpecT]]

    def __init__(
        self,
        fget: Callable[[_OwnerT], _ValueT],
        fset: Callable[[_OwnerT, _ValueT], None] | None = None,
        fdel: Callable[[_OwnerT], None] | None = None,
        *,
        config: _ConfigT,
    ) -> None:
        self.fget = fget
        self.fset = fset
        self.fdel = fdel

        self.__doc__ = getattr(fget, '__doc__', None)

        self._name: str | None = None
        self._config = config or self.config_type()
        self._spec: _SpecT | None = None
        self._owner: type[_OwnerT] | None = None

    def __set_name__(self, owner: type[_OwnerT], name: str) -> None:
        self._name = name
        self._owner = owner

    @property
    def spec(self) -> _SpecT:
        """Return the lazily resolved field specification."""
        if self._spec is None:
            self._spec = self._build_spec()

        return self._spec

    @property
    def model_field_info(self) -> ModelFieldInfo | None:
        """Return optional Pydantic-specific field configuration."""
        return self._config.model_field_info

    @property
    def model_adapter(self) -> ModelAdapter[t.Any, t.Any, t.Any] | None:
        """Return the entity/model value adapter."""
        return self._config.model_adapter

    @property
    def adapted_type(self) -> t.Any:
        """Return the externally adapted representation type."""
        if self.model_adapter is not None:
            return self.model_adapter.model_type

        return self.spec.value_type

    @property
    def cli_field_info(self) -> CliFieldInfo | None:
        """Return optional CLI-specific field configuration."""
        return self._config.cli_field_info

    @property
    def cli_adapter(self) -> CliAdapter[t.Any, t.Any] | None:
        """Return the model/CLI value adapter."""
        return self._config.cli_adapter

    @property
    def title(self) -> str:
        """Return the human-readable field title."""
        if self.model_field_info is not None and self.model_field_info.title is not None:
            return self.model_field_info.title

        return self.spec.name.replace('_', ' ').title()

    def getter(self, fget: Callable[[_OwnerT], _ValueT], /) -> Self:
        """Set the getter and return this descriptor."""
        self.fget = fget
        self.__doc__ = getattr(fget, '__doc__', None)
        self._spec = None
        return self

    def _build_spec(self, **kwargs: t.Any) -> _SpecT:
        """Resolve the declaration into the canonical specification."""
        spec = self.spec_type(
            **self._base_spec_values(),
            readonly=self._config.readonly,
            required_once_stored=self._config.required_once_stored,
            **kwargs,
        )

        if spec.required_once_stored and not is_nullable(spec.value_type):
            raise TypeError(f'{spec.name!r} cannot declare required_once_stored with a non-nullable type')

        return spec

    def _base_spec_values(self) -> dict[str, t.Any]:
        """Return values shared by all field specifications."""
        if self._name is None:
            raise RuntimeError('field has not been assigned to a class')

        value_type = t.get_type_hints(self.fget).get('return', t.Any)

        return {
            'name': self._name,
            'value_type': value_type,
            'description': (self.__doc__ or '').strip(),
        }


class EntityField(
    BaseField[
        _OwnerT,
        _ValueT,
        _QbFieldT,
        EntityFieldSpec,
        EntityFieldConfig,
    ],
):
    """Descriptor declaring an ORM entity field."""

    config_type = EntityFieldConfig
    spec_type = EntityFieldSpec

    def __init__(
        self,
        fget: Callable[[_OwnerT], _ValueT],
        fset: Callable[[_OwnerT, _ValueT], None] | None = None,
        fdel: Callable[[_OwnerT], None] | None = None,
        *,
        config: EntityFieldConfig | None = None,
    ) -> None:
        super().__init__(fget, fset, fdel, config=config or EntityFieldConfig())
        self._qb_field: _QbFieldT | None = None

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
                raise AttributeError('ORM entity field must be accessed through an entity class')

            return self._get_qb_field(owner)

        return self.fget(instance)

    def __set__(self, instance: _OwnerT, value: _ValueT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('field has not been assigned to an entity')

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.fset is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no setter')

        if instance.is_stored and self.spec.immutable:
            raise exceptions.ModificationNotAllowed(f'{self._owner.__name__}.{self._name} is immutable once stored')

        self.fset(instance, value)

    def __delete__(self, instance: _OwnerT) -> None:
        if self._owner is None or self._name is None:
            raise RuntimeError('field has not been assigned to an entity')

        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')

        if self.fdel is None:
            raise AttributeError(f'{self._owner.__name__}.{self._name} has no deleter')

        if instance.is_stored and self.spec.immutable:
            raise exceptions.ModificationNotAllowed(
                f'{self._owner.__name__}.{self._name} cannot be deleted after storing'
            )

        self.fdel(instance)

    def getter(self, fget: Callable[[_OwnerT], _ValueT], /) -> Self:
        """Set the getter and return this descriptor."""
        super().getter(fget)
        self._qb_field = None
        return self

    def setter(self, fset: Callable[[_OwnerT, _ValueT], None], /) -> Self:
        """Set the setter and return this descriptor."""
        if self._config.readonly:
            raise TypeError('cannot define a setter for a read-only ORM entity field')

        self.fset = fset
        self._spec = None

        return self

    def deleter(self, fdel: Callable[[_OwnerT], None], /) -> Self:
        """Set the deleter and return this descriptor."""
        if self._config.readonly:
            raise TypeError('cannot define a deleter for a read-only ORM entity field')

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

    def _get_qb_field(self, owner: type[_OwnerT]) -> _QbFieldT:
        """Return the lazily read-only QueryBuilder field."""
        if self._qb_field is None:
            self._qb_field = self._build_qb_field()

        return self._qb_field

    def _build_spec(self, **kwargs) -> EntityFieldSpec:
        """Resolve descriptor structure into the canonical field specification."""
        if self._name is None:
            raise RuntimeError('field has not been assigned to an entity')

        if self._config.readonly and self._config.updatable:
            raise TypeError(f'{self._name!r} cannot be both read-only and updatable')

        if self._config.readonly and self.fset is not None:
            raise TypeError(f'{self._name!r} is read-only but defines a setter')

        if self._config.updatable and self.fset is None:
            raise TypeError(f'{self._name!r} is declared updatable but defines no setter')

        return super()._build_spec(
            backend_key=self._config.backend_key or self._name,
            updatable=self._config.updatable,
            may_be_large=self._config.may_be_large,
        )


_FieldT = t.TypeVar('_FieldT', bound=BaseField)


class BaseFieldDecorator(
    t.Generic[
        _OwnerT,
        _ValueT,
        _ConfigT,
        _FieldT,
    ]
):
    """Common decorator-factory mechanics for typed field declarations."""

    config_type: Callable[..., _ConfigT]
    field_type: Callable[..., _FieldT]

    def __init__(self, config: _ConfigT | None = None) -> None:
        self._config = config or self.config_type()

    def _call(
        self,
        fget: Callable[..., t.Any] | None = None,
        /,
        **kwargs: t.Any,
    ) -> _FieldT | Self:
        if fget is None:
            return type(self)(self.config_type(**kwargs))

        return self.field_type(fget, config=self._config)


_ConfiguredQbFieldT = t.TypeVar('_ConfiguredQbFieldT', bound=qb_fields.QbField)


class ConfiguredFieldDecorator(t.Protocol[_ConfiguredQbFieldT]):
    """Configured field decorator with a known QueryBuilder field type."""

    def __call__(
        self,
        fget: Callable[[_OwnerT], _ValueT],
        /,
    ) -> EntityField[_OwnerT, _ValueT, _ConfiguredQbFieldT]: ...


_AdaptedEntityT = t.TypeVar('_AdaptedEntityT')
_AdaptedModelT = t.TypeVar('_AdaptedModelT')


class EntityFieldDecorator(
    BaseFieldDecorator[
        _OwnerT,
        _ValueT,
        EntityFieldConfig,
        EntityField[t.Any, t.Any, qb_fields.QbField],
    ],
):
    """Decorator for entity fields."""

    config_type = EntityFieldConfig
    field_type = EntityField

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], int],
        /,
    ) -> EntityField[_OwnerT, int, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], int | None],
        /,
    ) -> EntityField[_OwnerT, int | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], float],
        /,
    ) -> EntityField[_OwnerT, float, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], float | None],
        /,
    ) -> EntityField[_OwnerT, float | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], datetime.datetime],
        /,
    ) -> EntityField[_OwnerT, datetime.datetime, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], datetime.datetime | None],
        /,
    ) -> EntityField[_OwnerT, datetime.datetime | None, qb_fields.QbNumericField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], str],
        /,
    ) -> EntityField[_OwnerT, str, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], str | None],
        /,
    ) -> EntityField[_OwnerT, str | None, qb_fields.QbStrField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], list[_ValueT]],
        /,
    ) -> EntityField[_OwnerT, list[_ValueT], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], list[_ValueT] | None],
        /,
    ) -> EntityField[_OwnerT, list[_ValueT] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], tuple[_ValueT, ...]],
        /,
    ) -> EntityField[_OwnerT, tuple[_ValueT, ...], qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], tuple[_ValueT, ...] | None],
        /,
    ) -> EntityField[_OwnerT, tuple[_ValueT, ...] | None, qb_fields.QbArrayField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], dict[str, _ValueT]],
        /,
    ) -> EntityField[_OwnerT, dict[str, _ValueT], qb_fields.QbDictField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        fget: Callable[[_OwnerT], dict[str, _ValueT] | None],
        /,
    ) -> EntityField[_OwnerT, dict[str, _ValueT] | None, qb_fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], object],
        /,
    ) -> EntityField[_OwnerT, object, qb_fields.QbAnyField]: ...

    @t.overload
    def __call__(  # type: ignore[overload-cannot-match]
        self,
        fget: Callable[[_OwnerT], _ValueT],
        /,
    ) -> EntityField[_OwnerT, _ValueT, qb_fields.QbAnyField]: ...

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
    ) -> ConfiguredFieldDecorator[_QbFieldT]: ...

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


field: EntityFieldDecorator = EntityFieldDecorator()


def iter_fields(entity: type) -> dict[str, EntityField]:
    """Return all effective ORM entity fields on an entity hierarchy."""
    result: dict[str, EntityField] = {}

    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, EntityField):
                result[name] = value
            elif name in result:
                del result[name]

    return result
