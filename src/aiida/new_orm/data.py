from __future__ import annotations

import typing as t

from .attributes import attribute
from .node import Node


class Data(Node, extra_attributes='allow'):
    """A data node."""

    _export_format_replacements: dict[str, str] = {}

    @attribute
    def source(self) -> dict[str, t.Any] | None:
        """Return the source of the node."""
        return self.base.attributes.get('source', None)

    @source.setter  # type: ignore[no-redef]
    def source(self, value: dict[str, t.Any] | None):
        self.base.attributes.set('source', value)

    @classmethod
    def get_class_node_type(cls) -> str:
        """Return the node type of the class."""
        return cls.class_node_type

    def export(self, path, fileformat=None, overwrite=False, **kwargs):
        """Save a Data object to a file."""
        import os

        if not path:
            raise ValueError('Path not recognized')

        if os.path.exists(path) and not overwrite:
            raise OSError(f'A file was already found at {path}')

        if fileformat is None:
            extension = os.path.splitext(path)[1]
            if extension.startswith(os.path.extsep):
                extension = extension[len(os.path.extsep) :]
            if not extension:
                raise ValueError('Cannot recognized the fileformat from the extension')

            # Replace the fileformat using the replacements specified in the
            # _export_format_replacements dictionary. If not found there,
            # by default assume the fileformat string is identical to the extension
            fileformat = self._export_format_replacements.get(extension, extension)

        retlist = []

        filetext, extra_files = self._exportcontent(fileformat, main_file_name=path, **kwargs)

        if not overwrite:
            for fname in extra_files:
                if os.path.exists(fname):
                    raise OSError(f'The file {fname} already exists, stopping.')

            if os.path.exists(path):
                raise OSError(f'The file {path} already exists, stopping.')

        for additional_fname, additional_fcontent in extra_files.items():
            retlist.append(additional_fname)
            with open(additional_fname, 'wb', encoding=None) as fhandle:
                fhandle.write(additional_fcontent)  # This is up to each specific plugin
        retlist.append(path)
        with open(path, 'wb', encoding=None) as fhandle:
            fhandle.write(filetext)

        return retlist

    @classmethod
    def get_export_formats(cls):
        """Get the list of valid export format strings"""
        exporter_prefix = '_prepare_'
        method_names = dir(cls)  # get list of class methods names
        valid_format_names = [
            i[len(exporter_prefix) :] for i in method_names if i.startswith(exporter_prefix)
        ]  # filter them
        return sorted(valid_format_names)

    def importstring(self, inputstring, fileformat, **kwargs):
        """Converts a Data object to other text format."""
        importers = self._get_importers()

        try:
            func = importers[fileformat]
        except KeyError:
            if importers.keys():
                raise ValueError(
                    'The format {} is not implemented for {}. Currently implemented are: {}.'.format(
                        fileformat, self.__class__.__name__, ','.join(importers.keys())
                    )
                )
            else:
                raise ValueError(
                    f'The format {fileformat} is not implemented for {self.__class__.__name__}. '
                    'No formats are implemented yet.'
                )

        # func is bound to self by getattr in _get_importers()
        func(inputstring, **kwargs)

    def importfile(self, fname, fileformat=None):
        """Populate a Data object from a file."""
        if fileformat is None:
            fileformat = fname.split('.')[-1]
        with open(fname, encoding='utf8') as fhandle:  # reads in cwd, if fname is not absolute
            self.importstring(fhandle.read(), fileformat)

    def convert(self, object_format=None, *args):
        """Convert the AiiDA StructureData into another python object"""
        if object_format is None:
            raise ValueError('object_format must be provided')

        if not isinstance(object_format, str):
            raise ValueError('object_format should be a string')

        converters = self._get_converters()

        try:
            func = converters[object_format]
        except KeyError:
            if converters.keys():
                raise ValueError(
                    'The format {} is not implemented for {}. Currently implemented are: {}.'.format(
                        object_format, self.__class__.__name__, ','.join(converters.keys())
                    )
                )
            else:
                raise ValueError(
                    f'The format {object_format} is not implemented for {self.__class__.__name__}. '
                    'No formats are implemented yet.'
                )

        return func(*args)

    def _exportcontent(self, fileformat, main_file_name='', **kwargs):
        """Converts a Data node to one (or multiple) files.

        Note: Export plugins should return utf8-encoded **bytes**, which can be
        directly dumped to file.
        """
        exporters = self._get_exporters()

        try:
            func = exporters[fileformat]
        except KeyError:
            if exporters.keys():
                raise ValueError(
                    'The format {} is not implemented for {}. Currently implemented are: {}.'.format(
                        fileformat, self.__class__.__name__, ','.join(exporters.keys())
                    )
                )
            else:
                raise ValueError(
                    f'The format {fileformat} is not implemented for {self.__class__.__name__}. '
                    'No formats are implemented yet.'
                )

        string, dictionary = func(main_file_name=main_file_name, **kwargs)
        assert isinstance(string, bytes), 'export function `{}` did not return the content as a byte string.'

        return string, dictionary

    def _get_exporters(self):
        """Get all implemented export formats.
        The convention is to find all _prepare_... methods.
        Returns a dictionary of method_name: method_function
        """
        # NOTE: To add support for a new format, write a new function called as
        # _prepare_"" with the name of the new format
        exporter_prefix = '_prepare_'
        valid_format_names = self.get_export_formats()
        valid_formats = {k: getattr(self, exporter_prefix + k) for k in valid_format_names}
        return valid_formats

    def _get_importers(self):
        """Get all implemented import formats.
        The convention is to find all _parse_... methods.
        Returns a list of strings.
        """
        # NOTE: To add support for a new format, write a new function called as
        # _parse_"" with the name of the new format
        importer_prefix = '_parse_'
        method_names = dir(self)  # get list of class methods names
        valid_format_names = [i[len(importer_prefix) :] for i in method_names if i.startswith(importer_prefix)]
        valid_formats = {k: getattr(self, importer_prefix + k) for k in valid_format_names}
        return valid_formats

    def _get_converters(self):
        """Get all implemented converter formats.
        The convention is to find all _get_object_... methods.
        Returns a list of strings.
        """
        # NOTE: To add support for a new format, write a new function called as
        # _prepare_"" with the name of the new format
        exporter_prefix = '_get_object_'
        method_names = dir(self)  # get list of class methods names
        valid_format_names = [i[len(exporter_prefix) :] for i in method_names if i.startswith(exporter_prefix)]
        valid_formats = {k: getattr(self, exporter_prefix + k) for k in valid_format_names}
        return valid_formats
