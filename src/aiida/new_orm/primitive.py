from __future__ import annotations

from aiida.new_orm.attributes import attribute
from aiida.new_orm.data import Data


class PrimitiveData(Data):
    """A class representing primitive data types."""

    @attribute
    def value(self) -> object:
        """The value of the primitive data."""
        return self.base.attributes.get('value', None)
