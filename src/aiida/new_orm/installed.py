from __future__ import annotations

import pathlib

from aiida.common import exceptions
from aiida.common.lang import type_check
from aiida.common.log import override_log_level

from .adapters import EntityPkAdapter, LabelPkAdapter, PathStrAdapter
from .attributes import attribute
from .code import Code
from .computer import Computer
from .fields import CliFieldInfo, ModelFieldInfo, field

__all__ = ('InstalledCode',)


class InstalledCode(Code):
    """Data plugin representing an executable code on a remote computer."""

    @field(
        model_field_info=ModelFieldInfo(description='The PK of the associated computer.'),
        model_adapter=EntityPkAdapter(Computer),
        cli_field_info=CliFieldInfo(
            help='The label of the associated computer.',
            priority=2,
            short_name='-Y',
        ),
        cli_adapter=LabelPkAdapter(Computer),
    )
    def computer(self) -> Computer:
        """The computer associated with the code."""
        if (computer := super().computer) is None:
            raise exceptions.ValidationError('the computer is not set for this code')

        return computer

    @computer.setter  # type: ignore[no-redef]
    def computer(self, computer: Computer) -> None:
        type_check(computer, Computer, allow_none=False)
        self.backend_entity.computer = computer.backend_entity

    @attribute(
        model_adapter=PathStrAdapter(),
        cli_field_info=CliFieldInfo(
            short_name='-X',
            priority=1,
        ),
    )
    def filepath_executable(self) -> pathlib.PurePath:
        """Filepath of the executable on the remote computer."""
        return pathlib.PurePath(self.base.attributes.get('filepath_executable'))

    @filepath_executable.setter  # type: ignore[no-redef]
    def filepath_executable(self, value: str) -> None:
        type_check(value, str)
        self.base.attributes.set('filepath_executable', value)

    @property
    def full_label(self) -> str:
        """Return the full label of this code."""
        return f'{self.label}@{self.computer.label}'

    def validate_filepath_executable(self):
        """Validate the ``filepath_executable`` attribute.

        Checks whether the executable exists on the remote computer if a transport can be opened to it. This method
        is intentionally not called in ``_validate`` as to allow the creation of ``Code`` instances whose computers can
        not yet be connected to and as to not require the overhead of opening transports in storing a new code.

        .. note:: If the ``filepath_executable`` is not an absolute path, the check is skipped.

        :raises `~aiida.common.exceptions.ValidationError`: if no transport could be opened or if the defined executable
            does not exist on the remote computer.
        """
        if not self.filepath_executable.is_absolute():
            return

        try:
            with override_log_level():  # Temporarily suppress noisy logging
                with self.computer.get_transport() as transport:
                    file_exists = transport.isfile(str(self.filepath_executable))
                    if file_exists:
                        mode = transport.get_mode(str(self.filepath_executable))
                        # `format(mode, 'b')` with default permissions
                        # gives 110110100, representing rw-rw-r--
                        # Check on index 2 if user has execute
                        user_has_execute = format(mode, 'b')[2] == '1'

        except Exception as exception:
            raise exceptions.ValidationError(
                'Could not connect to the configured computer to determine whether the specified executable exists.'
            ) from exception

        if not file_exists:
            raise exceptions.ValidationError(
                f'The provided remote absolute path `{self.filepath_executable}` does not exist on the computer.'
            )

        if not user_has_execute:
            execute_msg = (
                f'The file at the remote absolute path `{self.filepath_executable}` exists, '
                'but might not actually be executable. Check the permissions.'
            )
            raise exceptions.ValidationError(execute_msg)

    def can_run_on_computer(self, computer: Computer) -> bool:
        """Return whether the code can run on a given computer."""
        type_check(computer, Computer)
        return computer.pk == self.computer.pk

    def get_executable(self) -> pathlib.PurePath:
        """Return the executable that the submission script should execute to run the code."""
        return self.filepath_executable

    def _validate(self):
        """Validate the instance by checking that a computer has been defined."""
        super()._validate()

        if not self.computer:
            raise exceptions.ValidationError('The `computer` is undefined.')

        try:
            self.filepath_executable
        except TypeError as exception:
            raise exceptions.ValidationError('The `filepath_executable` is not set.') from exception
