from __future__ import annotations

import abc
import typing as t

from aiida.common.lang import classproperty
from aiida.orm import fields as qb_fields

_OrmValueT = t.TypeVar('_OrmValueT')
_ModelValueT = t.TypeVar('_ModelValueT')
_QbFieldT = t.TypeVar('_QbFieldT', bound=qb_fields.QbField)


class ModelAdapter(abc.ABC, t.Generic[_OrmValueT, _ModelValueT, _QbFieldT]):
    """Abstract base class for model adapters that convert between ORM and model values."""

    _model_type: t.ClassVar[t.Any] = None

    @classproperty
    def model_type(cls: type[ModelAdapter]) -> t.Any:  # noqa: N805
        """Return the model-side type inferred from `to_model`."""
        if cls._model_type is None:
            try:
                cls._model_type = t.get_type_hints(cls.to_model)['return']
            except KeyError:
                raise TypeError(f'`{cls.__name__}.to_model` must have a return annotation') from None

        return cls._model_type

    @abc.abstractmethod
    def to_model(self, value: _OrmValueT) -> _ModelValueT:
        """Convert an ORM value to its model representation."""

    @abc.abstractmethod
    def to_orm(self, value: _ModelValueT) -> _OrmValueT:
        """Convert a model value to its ORM representation."""
