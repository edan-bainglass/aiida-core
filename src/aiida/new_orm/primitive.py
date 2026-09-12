from __future__ import annotations

from aiida.new_orm.data import Data
from aiida.orm.decorators import attribute


class PrimitiveData(Data):
    """A class representing primitive data types."""

    @attribute
    def value(self) -> object:
        """The value of the primitive data."""
        return self.base.attributes.get('value', None)
