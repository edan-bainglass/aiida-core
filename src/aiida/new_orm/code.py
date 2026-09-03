from __future__ import annotations

import abc
import functools
import pathlib

from aiida.cmdline.params.options.interactive import TemplateInteractiveOption
from aiida.common import exceptions
from aiida.common.folders import Folder
from aiida.common.lang import type_check
from aiida.engine import ProcessBuilder
from aiida.plugins.factories import CalculationFactory

from .attributes import attribute
from .computer import Computer
from .data import Data
from .fields import CliFieldInfo, ModelFieldInfo, field


class Code(Data, abc.ABC):
    """Abstract data plugin representing an executable code."""

    _KEY_ATTRIBUTE_DEFAULT_CALC_JOB_PLUGIN: str = 'default_calc_job_plugin'
    _KEY_ATTRIBUTE_APPEND_TEXT: str = 'append_text'
    _KEY_ATTRIBUTE_PREPEND_TEXT: str = 'prepend_text'
    _KEY_ATTRIBUTE_USE_DOUBLE_QUOTES: str = 'use_double_quotes'
    _KEY_ATTRIBUTE_WITH_MPI: str = 'with_mpi'
    _KEY_ATTRIBUTE_WRAP_CMDLINE_PARAMS: str = 'wrap_cmdline_params'
    _KEY_EXTRA_IS_HIDDEN: str = 'is_hidden'

    def __str__(self):
        if self.computer is None:
            return f"Local code '{self.label}' pk: {self.pk}, uuid: {self.uuid}"

        return f"Remote code '{self.label}' on {self.computer.label} pk: {self.pk}, uuid: {self.uuid}"

    @field(
        cli_field_info=CliFieldInfo(
            short_name='-L',
            priority=4,
        ),
    )
    def label(self) -> str:
        """A unique label to identify the code by."""
        return self._backend_entity.label

    @label.setter  # type: ignore[no-redef]
    def label(self, value: str) -> None:
        type_check(value, str)

        if '@' in value:
            raise ValueError('The label contains a `@` symbol, which is not allowed.')

        self._backend_entity.label = value

    @field(
        updatable=True,
        model_field_info=ModelFieldInfo(default=''),
        cli_field_info=CliFieldInfo(
            short_name='-D',
            priority=3,
        ),
    )
    def description(self) -> str:
        """Human-readable description, ideally including version and compilation environment."""
        return self._backend_entity.description

    @description.setter  # type: ignore[no-redef]
    def description(self, value: str) -> None:
        type_check(value, str)

        self._backend_entity.description = value

    @attribute(
        model_field_info=ModelFieldInfo(
            default=None,
            title='Default `CalcJob` plugin',
        ),
        cli_field_info=CliFieldInfo(short_name='-P'),
    )
    def default_calc_job_plugin(self) -> str | None:
        """Entry point name of the default plugin (as listed in `verdi plugin list aiida.calculations`)."""
        return self.base.attributes.get(self._KEY_ATTRIBUTE_DEFAULT_CALC_JOB_PLUGIN, None)

    @default_calc_job_plugin.setter  # type: ignore[no-redef]
    def default_calc_job_plugin(self, value: str | None) -> None:
        type_check(value, str, allow_none=True)
        self.base.attributes.set(self._KEY_ATTRIBUTE_DEFAULT_CALC_JOB_PLUGIN, value)

    @attribute(
        model_field_info=ModelFieldInfo(
            default=False,
            title='Escape using double quotes',
        ),
    )
    def use_double_quotes(self) -> bool:
        """Whether to escape the command line invocation of this code with double quotes."""
        return self.base.attributes.get(self._KEY_ATTRIBUTE_USE_DOUBLE_QUOTES, False)

    @use_double_quotes.setter  # type: ignore[no-redef]
    def use_double_quotes(self, value: bool) -> None:
        type_check(value, bool)
        self.base.attributes.set(self._KEY_ATTRIBUTE_USE_DOUBLE_QUOTES, value)

    @attribute(
        model_field_info=ModelFieldInfo(
            default=None,
            title='Run with MPI',
        ),
        cli_field_info=CliFieldInfo(
            help=(
                'Specify whether the executable should be run with MPI.'
                ' If left unspecified, it will be determined by the calculation job plugin or inputs.'
            )
        ),
    )
    def with_mpi(self) -> bool | None:
        """Whether the executable should be run as an MPI program."""
        return self.base.attributes.get(self._KEY_ATTRIBUTE_WITH_MPI, None)

    @with_mpi.setter  # type: ignore[no-redef]
    def with_mpi(self, value: bool | None) -> None:
        type_check(value, bool, allow_none=True)
        self.base.attributes.set(self._KEY_ATTRIBUTE_WITH_MPI, value)

    @attribute(
        model_field_info=ModelFieldInfo(
            default=False,
            title='Wrap command line parameters in double quotes',
        ),
        cli_field_info=CliFieldInfo(
            help=(
                'Specify whether all command line parameters to be passed to the engine command should be wrapped'
                ' in double quotes. This should be set to `True` for Docker.'
            )
        ),
    )
    def wrap_cmdline_params(self) -> bool:
        """Whether to wrap all command line parameters in double quotes."""
        return self.base.attributes.get(self._KEY_ATTRIBUTE_WRAP_CMDLINE_PARAMS, False)

    @wrap_cmdline_params.setter  # type: ignore[no-redef]
    def wrap_cmdline_params(self, value: bool) -> None:
        type_check(value, bool)
        self.base.attributes.set(self._KEY_ATTRIBUTE_WRAP_CMDLINE_PARAMS, value)

    @attribute(
        model_field_info=ModelFieldInfo(
            default='',
            title='Append script',
        ),
        cli_field_info=CliFieldInfo(
            option_cls=functools.partial(
                TemplateInteractiveOption,
                extension='.bash',
                header='APPEND_TEXT: if there is any bash commands that should be appended to the executable call '
                'in all submit scripts for this code, type that between the equal signs below and save the file.',
                footer='All lines that start with `#=`: will be ignored.',
            ),
        ),
    )
    def append_text(self) -> str:
        """Bash commands that should be appended to the run line in all submit scripts for this code."""
        return self.base.attributes.get(self._KEY_ATTRIBUTE_APPEND_TEXT, '')

    @append_text.setter  # type: ignore[no-redef]
    def append_text(self, value: str) -> None:
        type_check(value, str, allow_none=True)
        self.base.attributes.set(self._KEY_ATTRIBUTE_APPEND_TEXT, value)

    @attribute(
        model_field_info=ModelFieldInfo(
            default='',
            title='Prepend script',
        ),
        cli_field_info=CliFieldInfo(
            option_cls=functools.partial(
                TemplateInteractiveOption,
                extension='.bash',
                header='PREPEND_TEXT: if there is any bash commands that should be prepended to the executable call '
                'in all submit scripts for this code, type that between the equal signs below and save the file.',
                footer='All lines that start with `#=`: will be ignored.',
            ),
        ),
    )
    def prepend_text(self) -> str:
        """Bash commands that should be prepended to the run line in all submit scripts for this code."""
        return self.base.attributes.get(self._KEY_ATTRIBUTE_PREPEND_TEXT, '')

    @prepend_text.setter  # type: ignore[no-redef]
    def prepend_text(self, value: str) -> None:
        type_check(value, str, allow_none=True)
        self.base.attributes.set(self._KEY_ATTRIBUTE_PREPEND_TEXT, value)

    @property
    def is_hidden(self) -> bool:
        """Whether the code is hidden."""
        return self.base.extras.get(self._KEY_EXTRA_IS_HIDDEN, False)

    @is_hidden.setter
    def is_hidden(self, value: bool) -> None:
        type_check(value, bool)
        self.base.extras.set(self._KEY_EXTRA_IS_HIDDEN, value)

    @abc.abstractmethod
    def can_run_on_computer(self, computer: Computer) -> bool:
        """Return whether the code can run on a given computer."""

    @abc.abstractmethod
    def get_executable(self) -> pathlib.PurePath:
        """Return the executable that the submission script should execute to run the code."""

    def get_executable_cmdline_params(self, cmdline_params: list[str] | None = None) -> list:
        """Return the list of executable with its command line parameters."""
        return [str(self.get_executable())] + (cmdline_params or [])

    def get_prepend_cmdline_params(
        self,
        mpi_args: list[str] | None = None,
        extra_mpirun_params: list[str] | None = None,
    ) -> list[str]:
        """Return List of command line parameters to be prepended to the executable in submission line."""
        return (mpi_args or []) + (extra_mpirun_params or [])

    def validate_working_directory(self, folder: Folder):
        """Validate content of the working directory created by the :class:`~aiida.engine.CalcJob` plugin."""

    @property
    @abc.abstractmethod
    def full_label(self) -> str:
        """Return the full label of this code."""

    def get_builder(self) -> ProcessBuilder:
        """Create and return a new ``ProcessBuilder`` for the ``CalcJob`` class of the plugin configured for this code.

        The configured calculation plugin class is defined by the ``default_calc_job_plugin`` property.
        """
        entry_point = self.default_calc_job_plugin

        if entry_point is None:
            raise ValueError('No default calculation input plugin specified for this code')

        try:
            process_class = CalculationFactory(entry_point)
        except exceptions.EntryPointError:
            raise exceptions.EntryPointError(f'The calculation entry point `{entry_point}` could not be loaded')

        builder = process_class.get_builder()  # type: ignore[union-attr]
        builder.code = self

        return builder

    def _prepare_yaml(self, *args, **kwargs) -> tuple[bytes | str | None, dict]:
        """Export code to a YAML file."""
        import pathlib

        import yaml

        from .cli import EntityCliCreateSpec

        code_data = EntityCliCreateSpec(type(self)).serialize(
            self,
            context={
                'repository_dump_path': pathlib.Path.cwd() / self.label,
            },
            exclude_none=True,
        )

        return (
            yaml.dump(
                code_data,
                sort_keys=kwargs.get('sort', False),
                encoding='utf-8',
            ),
            {},
        )

    def _prepare_yml(self, *args, **kwargs) -> tuple[bytes | str | None, dict]:
        """Also allow for export as .yml"""
        return self._prepare_yaml(*args, **kwargs)
