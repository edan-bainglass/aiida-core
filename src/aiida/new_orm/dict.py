from __future__ import annotations

import typing as t
from copy import deepcopy

from aiida.common import exceptions

from .attributes import attribute
from .data import Data
from .primitive import PrimitiveData


class Dict(PrimitiveData):
    """A class representing a dictionary as a primitive data type."""

    @attribute
    def value(self) -> dict[str, t.Any]:
        return super().value

    @value.setter  # type: ignore[no-redef]
    def value(self, new_value: dict[str, t.Any]):
        self.base.attributes.set('value', new_value)

    def __getitem__(self, key):
        try:
            return self.value.get(key)
        except AttributeError as exc:
            raise KeyError from exc

    def __setitem__(self, key, value):
        self.base.attributes.set('value', {**self.value, key: value})

    def __eq__(self, other):
        if isinstance(other, Dict):
            return self.get_dict() == other.get_dict()
        return self.get_dict() == other

    def __contains__(self, key: str) -> bool:
        return key in self.value

    def __delitem__(self, key):
        try:
            new_value = {k: v for k, v in self.value.items() if k != key}
            self.base.attributes.set('value', new_value)
        except AttributeError as exc:
            raise KeyError from exc

    def get(self, key: str, default: t.Any | None = None, /) -> t.Any | None:
        """Return the value for key if key is in the dictionary, else default."""
        return self.value.get(key, default)

    def set_dict(self, dictionary) -> None:
        """Replace the current dictionary with another one."""
        dictionary_backup = deepcopy(self.get_dict())

        try:
            # Clear existing attributes and set the new dictionary
            self.value.clear()
            self.update(dictionary)
        except exceptions.ModificationNotAllowed:
            # I reraise here to avoid to go in the generic 'except' below that would raise the same exception again
            raise
        except Exception:
            # Try to restore the old data
            self.value.clear()
            self.update(dictionary_backup)
            raise

    def update(self, dictionary: dict[str, t.Any]) -> None:
        """Update the current dictionary with the keys provided in the dictionary."""
        for key, value in dictionary.items():
            self[key] = value

    def get_dict(self) -> dict[str, t.Any]:
        """Return a dictionary with the parameters currently set."""
        return dict(self.value)

    def keys(self) -> t.Generator[str, None, None]:
        """Iterator of valid keys stored in the Dict object."""
        yield from self.value.keys()

    def items(self) -> t.Generator[tuple[str, t.Any], None, None]:
        """Iterator of all items stored in the Dict node."""
        yield from self.value.items()

    @property
    def dict(self):
        """Return the value of the node as an instance of `AttributeManager`."""
        from aiida.orm.utils.managers import AttributeManager

        return AttributeManager(Data(attributes=self.value))
