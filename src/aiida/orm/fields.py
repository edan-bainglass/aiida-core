###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Module which provides decorators for AiiDA ORM entity -> DB field mappings."""
from abc import ABCMeta
from copy import deepcopy
from functools import singledispatchmethod
from pprint import pformat
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union

from pydantic import BaseModel

from aiida.common.pydantic import get_metadata

__all__ = ('QbAttrField', 'QbField', 'QbFields', 'QbFieldFilters')


class QbField:
    """A field of an ORM entity, accessible via the ``QueryBuilder``"""

    __slots__ = ('_key', '_qb_field', '_doc', '_dtype', '_subscriptable')

    def __init__(
        self,
        key: str,
        qb_field: Optional[str] = None,
        *,
        dtype: Optional[Any] = None,
        doc: str = '',
        subscriptable: bool = False,
    ) -> None:
        """Initialise a ORM entity field, accessible via the ``QueryBuilder``

        :param key: The key of the field on the ORM entity
        :param qb_field: The name of the field in the QueryBuilder, if not equal to ``key``
        :param dtype: The data type of the field. If None, the field is of variable type.
        :param doc: A docstring for the field
        :param subscriptable: If True, a new field can be created by ``field["subkey"]``
        """
        self._key = key
        self._qb_field = qb_field if qb_field is not None else key
        self._doc = doc
        self._dtype = dtype
        self._subscriptable = subscriptable

    @property
    def key(self) -> str:
        return self._key

    @property
    def qb_field(self) -> str:
        return self._qb_field

    @property
    def doc(self) -> str:
        return self._doc

    @property
    def dtype(self) -> Optional[Any]:
        return self._dtype

    @property
    def subscriptable(self) -> bool:
        return self._subscriptable

    def _repr_type(self, value: Any) -> str:
        """Return a string representation of the type of the value"""
        if value == type(None):
            return 'None'
        if isinstance(value, type):
            # basic types like int, str, etc.
            return value.__qualname__
        if hasattr(value, '__origin__') and value.__origin__ == Union:
            return 'typing.Union[' + ','.join(self._repr_type(t) for t in value.__args__) + ']'
        return str(value)

    def __repr__(self) -> str:
        dtype = self._repr_type(self.dtype) if self.dtype else ''
        return (
            f'{self.__class__.__name__}({self.key!r}'
            + (f', {self._qb_field!r}' if self._qb_field != self.key else '')
            + (f', dtype={dtype}' if self.dtype else '')
            + (f', subscriptable={self.subscriptable!r}' if self.subscriptable else '')
            + ')'
        )

    def __str__(self) -> str:
        type_str = (
            '?' if self.dtype is None else (self.dtype.__name__ if isinstance(self.dtype, type) else str(self.dtype))
        )
        type_str = type_str.replace('typing.', '')
        return f"{self.__class__.__name__}({self.qb_field}{'.*' if self.subscriptable else ''}) -> {type_str}"

    def __getitem__(self, key: str) -> 'QbField':
        """Return a new QbField with a nested key."""
        if not self.subscriptable:
            raise IndexError('This field is not subscriptable')
        return self.__class__(f'{self.key}.{key}', f'{self.qb_field}.{key}')

    def __hash__(self):
        return hash((self.key, self.qb_field))

    # methods for creating QueryBuilder filter objects
    # these methods mirror the syntax within SQLAlchemy

    def __eq__(self, value):
        return QbFieldFilters(((self, '==', value),))

    def __ne__(self, value):
        return QbFieldFilters(((self, '!=', value),))

    def __lt__(self, value):
        return QbFieldFilters(((self, '<', value),))

    def __le__(self, value):
        return QbFieldFilters(((self, '<=', value),))

    def __gt__(self, value):
        return QbFieldFilters(((self, '>', value),))

    def __ge__(self, value):
        return QbFieldFilters(((self, '>=', value),))

    def like(self, value: str):
        """Return a filter for only string values matching the wildcard string.

        - The percent sign (`%`) represents zero, one, or multiple characters
        - The underscore sign (`_`) represents one, single character
        """
        if not isinstance(value, str):
            raise TypeError('like must be a string')
        return QbFieldFilters(((self, 'like', value),))

    def ilike(self, value: str):
        """Return a filter for only string values matching the (case-insensitive) wildcard string.

        - The percent sign (`%`) represents zero, one, or multiple characters
        - The underscore sign (`_`) represents one, single character
        """
        if not isinstance(value, str):
            raise TypeError('ilike must be a string')
        return QbFieldFilters(((self, 'ilike', value),))

    def in_(self, value: Iterable[Any]):
        """Return a filter for only values in the list"""
        try:
            value = set(value)
        except TypeError:
            raise TypeError('in_ must be iterable')
        return QbFieldFilters(((self, 'in', value),))

    def not_in(self, value: Iterable[Any]):
        """Return a filter for only values not in the list"""
        try:
            value = set(value)
        except TypeError:
            raise TypeError('in_ must be iterable')
        return QbFieldFilters(((self, '!in', value),))

    # JSONB only, we should only show these if the field is a JSONB field

    # def contains(self, value):
    #     """Return a filter for only values containing these items"""
    #     return QbFieldFilters(((self, 'contains', value),))

    # def has_key(self, value):
    #     """Return a filter for only values with these keys"""
    #     return QbFieldFilters(((self, 'has_key', value),))

    # def of_length(self, value: int):
    #     """Return a filter for only array values of this length."""
    #     if not isinstance(value, int):
    #         raise TypeError('of_length must be an integer')
    #     return QbFieldFilters(((self, 'of_length', value),))

    # def longer(self, value: int):
    #     """Return a filter for only array values longer than this length."""
    #     if not isinstance(value, int):
    #         raise TypeError('longer must be an integer')
    #     return QbFieldFilters(((self, 'longer', value),))

    # def shorter(self, value: int):
    #     """Return a filter for only array values shorter than this length."""
    #     if not isinstance(value, int):
    #         raise TypeError('shorter must be an integer')
    #     return QbFieldFilters(((self, 'shorter', value),))


class QbAttrField(QbField):
    """An attribute field of an ORM entity, accessible via the ``QueryBuilder``"""

    @property
    def qb_field(self) -> str:
        return f'attributes.{self._qb_field}'


class QbFieldFilters:
    """An representation of a list of fields and their comparators."""

    __slots__ = ('filters',)

    def __init__(self, filters: Union[Sequence[Tuple[QbField, str, Any]], dict]):
        self.filters: Dict[str, Any] = {}
        self.add_filters(filters)

    def as_dict(self) -> Dict[str, Any]:
        """Return the filters dictionary."""
        return self.filters

    def items(self):
        """Return an items view of the filters for use in the QueryBuilder."""
        return self.filters.items()

    @singledispatchmethod
    def add_filters(self, filters: dict):
        self.filters.update(filters)

    @add_filters.register(list)
    @add_filters.register(tuple)
    def _(self, filters):
        for field, comparator, value in filters:
            qb_field = field.qb_field
            if qb_field in self.filters:
                self.filters['and'] = [
                    {qb_field: self.filters.pop(qb_field)},
                    {qb_field: {comparator: value}},
                ]
            else:
                self.filters[qb_field] = {comparator: value}

    def __repr__(self) -> str:
        return f'QbFieldFilters({self.filters})'

    def __getitem__(self, key: str) -> Any:
        return self.filters[key]

    def __contains__(self, key: str) -> bool:
        return key in self.filters

    def __eq__(self, other: object) -> bool:
        """``a == b`` checks if `a.filters == b.filters`."""
        if not isinstance(other, QbFieldFilters):
            raise TypeError(f'Cannot compare QbFieldFilters to {type(other)}')
        return self.filters == other.filters

    def __and__(self, other: 'QbFieldFilters') -> 'QbFieldFilters':
        """``a & b`` -> {'and': [`a.filters`, `b.filters`]}."""
        return self.__checks(other, 'and') or QbFieldFilters({'and': [self.filters, other.filters]})

    def __or__(self, other: 'QbFieldFilters') -> 'QbFieldFilters':
        """``a | b`` -> {'or': [`a.filters`, `b.filters`]}."""
        return self.__checks(other, 'or') or QbFieldFilters({'or': [self.filters, other.filters]})

    def __checks(self, other: 'QbFieldFilters', logical: str) -> Optional['QbFieldFilters']:
        """Check for redundant filters and nested logical operators."""

        if not isinstance(other, QbFieldFilters):
            raise TypeError(f'Cannot combine QbFieldFilters and {type(other)}')

        # same filters
        if other == self:
            return self

        # self is already wrapped in `logical`
        # append other to collection
        if logical in self.filters:
            self.filters[logical].append(other.filters)
            return self

        return None


class QbFields:
    """A readonly class for mapping attributes to database fields of an AiiDA entity."""

    __isabstractmethod__ = False

    def __init__(self, fields: Optional[Dict[str, QbField]] = None):
        self._fields = fields or {}

    def __repr__(self) -> str:
        return pformat({key: str(value) for key, value in self._fields.items()})

    def __str__(self) -> str:
        return str({key: str(value) for key, value in self._fields.items()})

    def __getitem__(self, key: str) -> QbField:
        """Return an QbField by key."""
        return self._fields[key]

    def __getattr__(self, key: str) -> QbField:
        """Return an QbField by key."""
        try:
            return self._fields[key]
        except KeyError:
            raise AttributeError(key)

    def __contains__(self, key: str) -> bool:
        """Return if the field key exists"""
        return key in self._fields

    def __len__(self) -> int:
        """Return the number of fields"""
        return len(self._fields)

    def __iter__(self):
        """Iterate through the field keys"""
        return iter(self._fields)

    def __dir__(self):
        """Return keys for tab competion."""
        return list(self._fields) + ['_dict']

    @property
    def _dict(self):
        """Return a copy of the internal mapping"""
        return deepcopy(self._fields)


class EntityFieldMeta(ABCMeta):
    """A metaclass for entity fields, which adds a `fields` class attribute."""

    def __new__(cls, name, bases, classdict):
        if 'Model' in classdict:
            if parent_models := [base.Model for base in bases if hasattr(base, 'Model')]:
                model = type('Model', (classdict['Model'], *parent_models), {})
            else:
                model = type('Model', (classdict['Model'], BaseModel), {})
            classdict['Model'] = model
        return super().__new__(cls, name, bases, classdict)

    def __init__(cls, name, bases, classdict):
        super().__init__(name, bases, classdict)

        # only allow an existing fields attribute if has been generated from a subclass
        current_fields = getattr(cls, 'fields', None)
        if current_fields is not None and not isinstance(current_fields, QbFields):
            raise ValueError(f"class '{cls}' already has a `fields` attribute set")

        fields = {}

        # If the class has an attribute ``Model`` that is a subclass of :class:`pydantic.BaseModel`, parse the model
        # fields to build up the ``fields`` class attribute, which is used to allow specifying ``QueryBuilder`` filters
        # programmatically.
        if hasattr(cls, 'Model') and issubclass(cls.Model, BaseModel):
            # If the class itself directly specifies the ``Model`` attribute, check that it is valid. Here, the check
            # ``cls.__dict__`` is used instead of ``hasattr`` as the former only returns true if the class itself
            # defines the attribute and does not just inherit it from a base class. In that case, this check will
            # already have been performed for that subclass.

            # When a class defines a ``Model``, the following check ensures that the model inherits from the same bases
            # as the class containing the attribute itself. For example, if ``cls`` inherits from ``ClassA`` and
            # ``ClassB`` that each define a ``Model``, the ``cls.Model`` class should inherit from both ``ClassA.Model``
            # and ``ClassBModel`` or it will be losing the attributes of some of the models.
            if 'Model' in cls.__dict__:
                # Get all the base classes in the MRO of this class that define a class attribute ``Model`` that is a
                # subclass of pydantic's ``BaseModel`` and not the class itself
                cls_bases_with_model = [
                    base
                    for base in cls.__mro__
                    if base is not cls and 'Model' in base.__dict__ and issubclass(base.Model, BaseModel)  # type: ignore[attr-defined]
                ]

                # Now get the "leaf" bases, i.e., those base classes in the subclass list that themselves do not have a
                # subclass in the tree. This set should be the base classes for the class' ``Model`` attribute.
                cls_bases_with_model_leaves = {
                    base
                    for base in cls_bases_with_model
                    if all(
                        not issubclass(b.Model, base.Model)  # type: ignore[attr-defined]
                        for b in cls_bases_with_model
                        if b is not base
                    )
                }

                cls_model_bases = {base.Model for base in cls_bases_with_model_leaves}  # type: ignore[attr-defined]

                # If the base class does not have a base that defines a model, it means the ``Model`` should simply have
                # ``pydantic.BaseModel`` as its sole base.
                if not cls_model_bases:
                    cls_model_bases = {
                        BaseModel,
                    }

            for key, field in cls.Model.model_fields.items():
                field_cls = QbAttrField if get_metadata(field, 'is_attribute', False) else QbField
                fields[key] = field_cls(
                    key,
                    qb_field=get_metadata(field, 'database_alias', None),
                    dtype=field.annotation,
                    doc=field.description,
                    subscriptable=get_metadata(field, 'subscriptable', False),
                )

        cls.fields = QbFields({key: fields[key] for key in sorted(fields)})
