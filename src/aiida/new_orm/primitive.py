from __future__ import annotations

from .attributes import attribute
from .data import Data


class PrimitiveData(Data):
    """A class representing primitive data types."""

    @attribute
    def value(self) -> object:
        """The value of the primitive data."""
        return self.base.attributes.get('value', None)
