from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from entity import Entity
    from node import Node

EntityType = t.TypeVar('EntityType', bound='Entity')
NodeType = t.TypeVar('NodeType', bound='Node')
