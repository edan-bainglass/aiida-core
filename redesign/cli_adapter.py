from __future__ import annotations

import abc
import typing as t

from aiida.common.lang import classproperty

_CliValueT = t.TypeVar('_CliValueT')
_ModelValueT = t.TypeVar('_ModelValueT')


class CliAdapter(abc.ABC, t.Generic[_CliValueT, _ModelValueT]):
    """Abstract base class for CLI adapters that convert between CLI and model values."""

    _cli_type: t.ClassVar[t.Any] = None

    @classproperty
    def cli_type(cls: type[CliAdapter]) -> t.Any:  # noqa: N805
        """Return the CLI-side type inferred from `to_model`."""
        if cls._cli_type is None:
            try:
                cls._cli_type = t.get_type_hints(cls.to_model)['value']
            except KeyError:
                raise TypeError(f'{cls.__name__}.to_model must annotate its `value` parameter') from None

        return cls._cli_type

    @abc.abstractmethod
    def to_model(self, value: _CliValueT) -> _ModelValueT:
        """Convert a CLI value to its model-side representation."""
