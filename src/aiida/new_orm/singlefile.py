###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Data class that can be used to store a single file in its repository."""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import typing as t

from aiida.common import exceptions
from aiida.common.typing import FilePath
from aiida.new_orm.attributes import attribute
from aiida.new_orm.data import Data

__all__ = ('SinglefileData',)


class SinglefileData(Data):
    """Data class that can be used to store a single file in its repository."""

    DEFAULT_FILENAME = 'file.txt'

    @classmethod
    def from_path(
        cls,
        filepath: FilePath,
        **kwargs: t.Any,
    ) -> SinglefileData:
        """Construct a new instance and set the contents from the given file path."""
        instance = cls(**kwargs)
        instance.set_file(filepath, kwargs.get('attributes', {}).get('filename'))
        return instance

    @classmethod
    def from_string(
        cls,
        content: str,
        **kwargs: t.Any,
    ) -> SinglefileData:
        """Construct a new instance and set ``content`` as its contents."""
        instance = cls(**kwargs)
        instance.set_file(io.StringIO(content), kwargs.get('attributes', {}).get('filename'))
        return instance

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        **kwargs: t.Any,
    ) -> SinglefileData:
        """Construct a new instance and set ``content`` as its contents."""
        instance = cls(**kwargs)
        instance.set_file(io.BytesIO(content), kwargs.get('attributes', {}).get('filename'))
        return instance

    @attribute(required_once_stored=True)
    def filename(self) -> str | None:
        """The name of the stored file."""
        filename = self.base.attributes.get('filename', None)
        if self.is_stored and filename is None:
            raise ValueError('Stored SinglefileData has no filename attribute.')
        return filename

    @filename.setter
    def filename(self, value: str) -> None:
        self.base.attributes.set('filename', value)

    @property
    def content(self) -> bytes:
        return self.get_content(mode='rb')

    @t.overload
    @contextlib.contextmanager
    def open(self, path: FilePath, mode: t.Literal['r'] = ...) -> t.Generator[t.TextIO, None, None]: ...

    @t.overload
    @contextlib.contextmanager
    def open(self, path: FilePath, mode: t.Literal['rb']) -> t.Generator[t.BinaryIO, None, None]: ...

    @t.overload
    @contextlib.contextmanager
    def open(self, path: None = None, mode: t.Literal['r'] = ...) -> t.Generator[t.TextIO, None, None]: ...

    @t.overload
    @contextlib.contextmanager
    def open(self, path: None = None, mode: t.Literal['rb'] = ...) -> t.Generator[t.BinaryIO, None, None]: ...

    @contextlib.contextmanager
    def open(
        self, path: FilePath | None = None, mode: t.Literal['r', 'rb'] = 'r'
    ) -> t.Generator[t.BinaryIO, None, None] | t.Generator[t.TextIO, None, None]:
        """Return an open file handle to the content of this data node."""
        if path is None:
            path = self.filename

        with self.base.repository.open(path, mode=mode) as handle:
            yield handle

    @contextlib.contextmanager
    def as_path(self) -> t.Generator[pathlib.Path, None, None]:
        """Make the contents of the file available as a normal filepath on the local file system."""
        with self.base.repository.as_path(self.filename) as filepath:
            yield filepath

    @t.overload
    def get_content(self, mode: t.Literal['rb']) -> bytes: ...

    @t.overload
    def get_content(self, mode: t.Literal['r']) -> str: ...

    def get_content(self, mode: str = 'r') -> str | bytes:
        """Return the content of the single file stored for this data node."""
        with self.open(mode=mode) as handle:  # type: ignore[call-overload]
            return handle.read()

    def set_file(
        self,
        file: FilePath | t.IO,
        filename: str | None = None,
    ) -> None:
        """Store the content of the file in the node's repository, deleting any other existing objects."""
        if isinstance(file, (str, pathlib.Path)):
            is_filelike = False

            key = os.path.basename(file)
            if not os.path.isabs(file):
                raise ValueError(f'path `{file}` is not absolute')

            if not os.path.isfile(file):
                raise ValueError(f'path `{file}` does not correspond to an existing file')
        else:
            is_filelike = True
            try:
                key = os.path.basename(file.name)
            except (AttributeError, TypeError):
                key = self.DEFAULT_FILENAME

        key = filename or key
        existing_object_names = self.base.repository.list_object_names()

        try:
            # Remove the 'key' from the list of currently existing objects such that it is not deleted after storing
            existing_object_names.remove(key)
        except ValueError:
            pass

        if is_filelike:
            self.base.repository.put_object_from_filelike(file, key)  # type: ignore[arg-type]
        else:
            self.base.repository.put_object_from_file(file, key)  # type: ignore[arg-type]

        # Delete any other existing objects (minus the current `key` which was already removed from the list)
        for existing_key in existing_object_names:
            self.base.repository.delete_object(existing_key)

        self.base.attributes.set('filename', key)

    def attach_file(self, filepath: str, fileobj: t.BinaryIO) -> None:
        self.set_file(fileobj, filepath)

    def _validate(self):
        """Validate the node before storing.

        This check ensures that there is exactly one file object stored in the repository,
        and that the filename attribute is set to the name of that object (forced).
        """
        super()._validate()

        objects = self.base.repository.list_object_names()

        if len(objects) != 1:
            raise exceptions.ValidationError(f'expected exactly one repository file, found {len(objects)}: {objects}')

        filename = objects[0]
        fileobj = self.base.repository.get_object(filename)
        if fileobj.is_dir():
            raise exceptions.ValidationError('expected a file, found a directory')

        self.base.attributes.set('filename', filename)
