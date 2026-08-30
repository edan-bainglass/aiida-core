from __future__ import annotations

import typing as t

from attributes import attribute
from node import Node


class Data(Node, extra_attributes='allow'):
    """A data node."""

    @attribute
    def source(self) -> dict[str, t.Any] | None:
        """Return the source of the node."""
        return self.base.attributes.get('source', None)

    @source.setter
    def source(self, value: dict[str, t.Any] | None):
        self.base.attributes.set('source', value)

    @classmethod
    def get_class_node_type(cls) -> str:
        """Return the node type of the class."""
        return cls.class_node_type
