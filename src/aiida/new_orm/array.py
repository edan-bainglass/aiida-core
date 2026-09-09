from __future__ import annotations

import typing as t
from collections.abc import Mapping, Sequence

import numpy as np
import pydantic as pdt
from typing_extensions import Self

from aiida.new_orm.data import Data

__all__ = ('ArrayData',)

_ArrayLike = Sequence[t.Any] | np.ndarray


class ArrayData(Data):
    """ORM representation of a node that stores one or more arrays."""

    _attributes_model_config = pdt.ConfigDict(
        extra='allow',
        json_schema_extra={
            'patternProperties': {
                r'^array\|[A-Za-z0-9_]+$': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'minItems': 1,
                    'description': 'Shape of an array stored in the repository',
                    'readOnly': True,
                }
            }
        },
    )

    array_prefix = 'array|'
    default_array_name = 'default'

    @classmethod
    def from_arrays(
        cls,
        arrays: _ArrayLike | Mapping[str, _ArrayLike],
        **kwargs: t.Any,
    ) -> Self:
        """Create an ArrayData from one or multiple arrays."""
        node = cls(**kwargs)

        if isinstance(arrays, (Sequence, np.ndarray)):
            arrays = {cls.default_array_name: arrays}

        if any(not isinstance(array, (Sequence, np.ndarray)) for array in arrays.values()):
            raise TypeError('`arrays` should be a single sequence or mapping of sequences')

        for name, array in arrays.items():
            node.set_array(name, np.asarray(array))

        return node

    def initialize(self):
        super().initialize()
        self._cached_arrays: dict[str, np.ndarray] = {}

    @property
    def arrays(self) -> dict[str, np.ndarray]:
        return {name: self.get_array(name) for name in self.get_arraynames()}

    def get_arraynames(self) -> list[str]:
        """Return a list of all arrays stored in the node, listing the files (and
        not relying on the properties)."""
        return self._arraynames_from_properties()

    def get_array(self, name: str | None = None) -> np.ndarray:
        """Return an array stored in the node"""
        if name is None:
            names = self.get_arraynames()
            num_arrays = len(names)

            if num_arrays == 0:
                raise ValueError('`name` not specified but the node contains no arrays.')
            if num_arrays > 1:
                raise ValueError('`name` not specified but the node contains multiple arrays.')

            name = names[0]

        def get_array_from_file(name: str) -> np.ndarray:
            """Return the array stored in a .npy file"""
            filename = f'{name}.npy'

            if filename not in self.base.repository.list_object_names():
                raise KeyError(f'Array with name `{name}` not found in ArrayData<{self.pk}>')

            # Open a handle in binary read mode as the arrays are written as binary files as well
            with self.base.repository.open(filename, mode='rb') as handle:
                return np.load(handle, allow_pickle=False)

        # Return with proper caching if the node is stored, otherwise always re-read from disk
        if not self.is_stored:
            return get_array_from_file(name)

        if name not in self._cached_arrays:
            self._cached_arrays[name] = get_array_from_file(name)

        return self._cached_arrays[name]

    def set_array(self, name: str, array: np.ndarray) -> None:
        """Store a new numpy array inside the node. Possibly overwrite the array
        if it already existed.
        """
        import tempfile

        if not isinstance(array, np.ndarray):
            raise TypeError('ArrayData can only store numpy arrays. Convert the object to an array first')

        # Check if the name is valid
        self._validate_array_name(name)

        # Write the array to a temporary file, and then add it to the repository of the node
        with tempfile.NamedTemporaryFile() as handle:
            np.save(handle, array, allow_pickle=False)

            # Flush and rewind the handle, otherwise the command to store it in the repo will write an empty file
            handle.flush()
            handle.seek(0)

            # Write the numpy array to the repository, keeping the byte representation
            self.base.repository.put_object_from_filelike(handle, f'{name}.npy')  # type: ignore[arg-type]

        # Store the array name and shape for querying purposes
        self.base.attributes.set(f'{self.array_prefix}{name}', list(array.shape))

    def attach_file(self, name: str, fileobj: t.BinaryIO) -> None:
        if not name.lower().endswith('.npy'):
            raise ValueError(f'expected .npy file: {name}')
        base = name.removesuffix('.npy')
        array = np.load(fileobj, allow_pickle=False)
        self.set_array(base, array)

    def _arraynames_from_files(self) -> list[str]:
        """Return a list of all arrays stored in the node, listing the files (and
        not relying on the properties).
        """
        return [i[:-4] for i in self.base.repository.list_object_names() if i.endswith('.npy')]

    def _arraynames_from_properties(self) -> list[str]:
        """Return a list of all arrays stored in the node, listing the attributes
        starting with the correct prefix.
        """
        return [i[len(self.array_prefix) :] for i in self.base.attributes.keys() if i.startswith(self.array_prefix)]

    def _validate_array_name(self, name: str) -> None:
        """Validate the array name.

        :param name: The name of the array.
        :raises ValueError: if the name is not valid.
        """
        import re

        if not name or re.sub('[0-9a-zA-Z_]', '', name):
            raise ValueError(
                f'The name assigned to the array ({name}) is not valid. '
                'It can only contain digits, letters and underscores'
            )

    def _validate(self) -> None:
        """Validate the consistency of stored array files and metadata."""
        from aiida.common.exceptions import ValidationError

        super()._validate()

        files = self._arraynames_from_files()
        properties = self._arraynames_from_properties()

        if not files:
            raise ValidationError('ArrayData must contain at least one array')

        if set(files) != set(properties):
            raise ValidationError(
                f'Mismatch of files and properties for ArrayData node (pk={self.pk}): {files} vs. {properties}'
            )
