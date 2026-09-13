from __future__ import annotations

import typing as t
from collections.abc import MutableSequence

import pydantic as pdt

from aiida.orm.decorators import attribute
from aiida.orm.nodes.data.base import to_aiida_type
from aiida.orm.nodes.data.data import Data

__all__ = ('List',)


class List(Data, MutableSequence[t.Any]):
    """ORM representation of a list node."""

    def __getitem__(self, item: t.Any) -> t.Any:
        return self.value[item]

    def __setitem__(self, key: t.Any, value: t.Any) -> None:
        data = self.value
        data[key] = value
        if not self._using_list_reference():
            self.value(data)

    def __delitem__(self, key: t.Any) -> None:
        data = self.value
        del data[key]
        if not self._using_list_reference():
            self.value(data)

    def __len__(self) -> int:
        return len(self.value)

    def __str__(self) -> str:
        return f'{super().__str__()} value: {self.value}'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, List):
            return self.value == other.value
        return self.value == other

    @attribute(model_field_info=pdt.fields.FieldInfo(title='List contents'))
    def value(self) -> list[t.Any]:
        """The list content."""
        return self.base.attributes.get('list', [])

    @value.setter
    def value(self, value: list[t.Any]) -> None:
        if not isinstance(value, list):
            raise TypeError('Must supply list type')
        self.base.attributes.set('list', value.copy())

    def append(self, value: t.Any) -> None:
        """Append an item to the list."""
        data = self.value
        data.append(value)
        if not self._using_list_reference():
            self.value(data)

    def extend(self, value: t.Iterable[t.Any]) -> None:
        """Extend the list by appending all the items from the iterable."""
        data = self.value
        data.extend(value)
        if not self._using_list_reference():
            self.value(data)

    def insert(self, i: int, value: t.Any) -> None:
        """Insert value at index i."""
        data = self.value
        data.insert(i, value)
        if not self._using_list_reference():
            self.value(data)

    def remove(self, value: t.Any) -> None:
        """Remove first occurrence of value."""
        data = self.value
        data.remove(value)
        if not self._using_list_reference():
            self.value(data)

    def pop(self, index: int = -1) -> t.Any:
        """Remove and return item at index (default last)."""
        data = self.value
        item = data.pop(index)
        if not self._using_list_reference():
            self.value(data)
        return item

    def index(self, value: t.Any, start: int = 0, stop: int | None = None) -> int:
        """Return first index of value."""
        if stop is None:
            return self.value.index(value, start)
        return self.value.index(value, start, stop)

    def count(self, value: t.Any) -> int:
        """Return number of occurrences of value."""
        return self.value.count(value)

    def sort(self, *, key: t.Callable[[t.Any], t.Any] | None = None, reverse: bool = False) -> None:
        """Sort the list in place."""
        data = self.value
        data.sort(key=key, reverse=reverse)
        if not self._using_list_reference():
            self.value(data)

    def reverse(self) -> None:
        """Reverse the list in place."""
        data = self.value
        data.reverse()
        if not self._using_list_reference():
            self.value(data)

    def _using_list_reference(self) -> bool:
        """This function tells the class if we are using a list reference. This
        means that calls to self.get_list return a reference rather than a copy
        of the underlying list and therefore self.set_list need not be called.
        This knowledge is essential to make sure this class is performant.

        Currently the implementation assumes that if the node needs to be
        stored then it is using the attributes cache which is a reference.

        :return: True if using self.get_list returns a reference to the underlying sequence. False otherwise.
        :rtype: bool
        """
        return not self.is_stored

    # TODO the following methods are handled above via property operations - consider removing

    def get_list(self) -> list[t.Any]:
        """Return the list content of this node.

        :return: a list
        """
        return self.list

    def set_list(self, data: list[t.Any]) -> None:
        """Set the list content of this node.

        :param data: the list to set
        """
        self.list = data


@to_aiida_type.register(list)
def _(value: list[t.Any]) -> List:
    return List(value=value)
