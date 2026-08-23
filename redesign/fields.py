from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable

from aiida.orm import fields

if t.TYPE_CHECKING:
    from redesign.entity import Entity

_UNSET = object()

_OwnerT = t.TypeVar('_OwnerT', bound='Entity')
_ValueT = t.TypeVar('_ValueT')
_FieldT = t.TypeVar('_FieldT', bound=fields.QbField)


@dataclasses.dataclass(frozen=True)
class FieldSpec:
    """Metadata for an `OrmField` descriptor."""

    name: str
    backend_key: str
    value_type: t.Any
    default: t.Any
    required: bool
    readonly: bool
    description: str
    example: t.Any


class OrmField(property, t.Generic[_OwnerT, _ValueT, _FieldT]):
    """A property exposing a `FieldSpec` for an ORM field on an entity class.

    The `FieldSpec` serves as a reference for the lazily-generated type-aware `QbField` and schemas field.
    """

    def __init__(
        self,
        fget: Callable[[_OwnerT], _ValueT] | None = None,
        fset: Callable[[_OwnerT, _ValueT], None] | None = None,
        fdel: Callable[[_OwnerT], None] | None = None,
        doc: str | None = None,
    ) -> None:
        super().__init__(fget, fset, fdel, doc)
        self._owner: type[_OwnerT] | None = None
        self._name: str | None = None
        self._spec: FieldSpec | None = None
        self._qb_field: _FieldT | None = None
        self._kwargs: dict[str, t.Any] = {}  # field metadata register used to generate the `FieldSpec`

    def __set_name__(self, owner: type[_OwnerT], name: str) -> None:
        self._owner = owner
        self._name = name

    @property
    def spec(self) -> FieldSpec:
        """Return a lazily-generated `FieldSpec`."""
        if self._spec is None:
            self._spec = self._build_spec()
        return self._spec

    @property
    def qb_field(self) -> _FieldT:
        """Return a lazily-generated, type-aware `QbField`."""
        if self._qb_field is None:
            spec = self.spec
            self._qb_field = fields.add_field(
                spec.backend_key,
                dtype=spec.value_type,
                doc=spec.description,
                is_attribute=False,
            )
        return self._qb_field

    @t.overload
    def __get__(self, instance: None, owner: type[_OwnerT]) -> _FieldT: ...

    @t.overload
    def __get__(self, instance: _OwnerT, owner: type[_OwnerT] | None = None) -> _ValueT: ...

    def __get__(self, instance: _OwnerT | None, owner: type[_OwnerT] | None = None) -> _ValueT | _FieldT:
        if instance is None:
            return self.qb_field
        return t.cast(_ValueT, super().__get__(instance, owner))

    def __set__(self, instance: _OwnerT, value: _ValueT) -> None:
        assert self._owner is not None and self._name is not None
        if self.spec.readonly:
            raise AttributeError(f'{self._owner.__name__}.{self._name} is read-only')
        if self.fset is None:  # TODO if owner is stored
            raise AttributeError(f'{self._owner.__name__}.{self._name} is immutable')
        super().__set__(instance, value)

    def setter(self, fset: Callable[[_OwnerT, _ValueT], None], /) -> OrmField[_OwnerT, _ValueT, _FieldT]:
        """Descriptor to obtain a copy of the property with a different setter.

        Overrides default `property.setter` to record the field metadata on the new `OrmField` instance.
        """
        result = t.cast(OrmField[_OwnerT, _ValueT, _FieldT], super().setter(fset))
        result._kwargs = self._kwargs
        return result

    def _build_spec(self) -> FieldSpec:
        if self._name is None:
            raise RuntimeError('field has not been assigned to an entity')
        if self.fget is None:
            raise TypeError(f'{self._name} has no getter')

        value_type = self._kwargs.get('value_type')
        if value_type is None:
            value_type = t.get_type_hints(self.fget).get('return', t.Any)

        default = self._kwargs.get('default', _UNSET)

        required = self._kwargs.get('required', False)
        if required and default is not _UNSET:
            raise TypeError(f'{self._name} cannot be required and have a default')
        if default is _UNSET:
            default = None

        return FieldSpec(
            name=self._name,
            backend_key=self._kwargs.get('backend_key', self._name),
            value_type=value_type,
            default=default,
            required=required,
            readonly=self._kwargs.get('readonly', False),
            description=self._kwargs.get('description', self.__doc__ or '').strip(),
            example=self._kwargs.get('example'),
        )


class OrmFieldDecorator:
    def __init__(self, kwargs: dict[str, t.Any] | None = None) -> None:
        self._kwargs = kwargs or {}

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], int],
    ) -> OrmField[_OwnerT, int, fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], float],
    ) -> OrmField[_OwnerT, float, fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], datetime.datetime],
    ) -> OrmField[_OwnerT, datetime.datetime, fields.QbNumericField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], str],
    ) -> OrmField[_OwnerT, str, fields.QbStrField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], list[_ValueT]],
    ) -> OrmField[_OwnerT, list[_ValueT], fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], tuple[_ValueT, ...]],
    ) -> OrmField[_OwnerT, tuple[_ValueT, ...], fields.QbArrayField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], dict[str, _ValueT]],
    ) -> OrmField[_OwnerT, dict[str, _ValueT], fields.QbDictField]: ...

    @t.overload
    def __call__(
        self,
        fget: Callable[[_OwnerT], _ValueT],
    ) -> OrmField[_OwnerT, _ValueT, fields.QbAnyField]: ...

    @t.overload
    def __call__(
        self,
        *,
        backend_key: str | None = None,
        value_type: type | None = None,
        default: t.Any = _UNSET,
        required: bool = False,
        readonly: bool = False,
        description: str | None = None,
        example: t.Any | None = None,
    ) -> t.Self:
        """Record ORM field metadata for the decorated property as a `FieldSpec`.

        `FieldSpec` serves as a reference for the lazily-generated type-aware `QbField` and schemas field.

        :param backend_key: the key of the field in the backend entity (used in querying)
        :type backend_key: str, optional
        :param value_type: the type of the field value
        :type value_type: type, optional
        :param default: the default value of the field
        :type default: any, optional
        :param required: whether the field is required (cannot be None)
        :type required: bool, optional
        :param readonly: whether the field is read-only (cannot be set)
        :type readonly: bool, optional
        :param description: the description of the field
        :type description: str, optional
        :param example: an example value of the field
        :type example: any, optional
        """

    def __call__(
        self,
        fget: Callable[[_OwnerT], _ValueT] | None = None,
        /,
        **kwargs: t.Any,
    ) -> t.Any:
        if fget is None:
            return type(self)(kwargs)
        field = OrmField(fget)
        field._kwargs = self._kwargs
        return field


field = OrmFieldDecorator()


def iter_fields(entity: type) -> dict[str, OrmField]:
    """Iterate over all `OrmField` descriptors defined on an entity class and its base classes.

    :param entity: the entity class
    :type entity: type
    :return: a dictionary mapping field names to `OrmField` descriptors
    :rtype: dict[str, OrmField]
    """
    result: dict[str, OrmField] = {}
    for base in reversed(entity.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, OrmField):
                result[name] = value
    return result
