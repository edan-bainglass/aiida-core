from __future__ import annotations

import dataclasses
import functools
import typing as t
from collections.abc import Callable

from pydantic.fields import FieldInfo as ModelFieldInfo
from typing_extensions import Self

from aiida.cmdline.params.options.interactive import TemplateInteractiveOption
from aiida.common.utils import is_nullable
from aiida.orm import fields as qb_fields

from .cli_adapter import CliAdapter
from .model_adapter import ModelAdapter

__all__ = (
    'BaseField',
    'BaseFieldConfig',
    'BaseFieldDecorator',
    'BaseFieldSpec',
    'CliFieldInfo',
    'ModelFieldInfo',
    'Storable',
)


@dataclasses.dataclass(frozen=True)
class BaseFieldSpec:
    """Base semantic description of an ORM field."""

    name: str
    value_type: t.Any
    description: str
    readonly: bool
    required_once_stored: bool


@dataclasses.dataclass(frozen=True)
class CliFieldInfo:
    """Optional Click-specific configuration for an ORM field."""

    prompt: str | bool | None = None
    help: str = ''
    priority: int = 0
    short_name: str = ''
    option_cls: functools.partial[TemplateInteractiveOption] | None = None


@dataclasses.dataclass(frozen=True)
class BaseFieldConfig:
    """Base unresolved configuration for an ORM field."""

    model_field_info: ModelFieldInfo | None = None
    model_adapter: ModelAdapter[t.Any, t.Any, t.Any] | None = None
    cli_field_info: CliFieldInfo | None = None
    cli_adapter: CliAdapter[t.Any, t.Any] | None = None
    readonly: bool = False
    required_once_stored: bool = False


class Storable(t.Protocol):
    """Protocol for ORM objects with storage lifecycle semantics."""

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
        self._owner: type[_OwnerT] | None = None
        self._config = config
        self._spec: _SpecT | None = None

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
        """Return the entity/model representation adapter."""
        return self._config.model_adapter

    @property
    def adapted_type(self) -> t.Any:
        """Return the model-adapted representation type."""
        if self.model_adapter is not None:
            return self.model_adapter.model_type

        return self.spec.value_type

    @property
    def cli_field_info(self) -> CliFieldInfo | None:
        """Return optional CLI-specific field configuration."""
        return self._config.cli_field_info

    @property
    def cli_adapter(self) -> CliAdapter[t.Any, t.Any] | None:
        """Return the model/CLI representation adapter."""
        return self._config.cli_adapter

    @property
    def title(self) -> str:
        """Return the human-readable title."""
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
            raise TypeError(f'{spec.name!r} cannot be required_once_stored because its declared type is not nullable')

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
