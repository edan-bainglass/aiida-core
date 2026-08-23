from __future__ import annotations

import typing as t

import pydantic as pdt
from fields import iter_fields

if t.TYPE_CHECKING:
    from entity import Entity


class OrmModel(pdt.BaseModel):
    """Base model for all ORM schemas."""

    model_config = pdt.ConfigDict(
        extra='forbid',
    )


class UnsupportedModelError(Exception):
    """Exception raised when an unsupported model is requested."""


_EntityT = t.TypeVar('_EntityT', bound='Entity')
_ModelName = t.Literal['read', 'create', 'update']


class ModelsNamespace(t.Generic[_EntityT]):
    """Lazily generated model projections for one entity class."""

    _names: t.ClassVar[set[_ModelName]] = {'read', 'create', 'update'}

    def __init__(self) -> None:
        self._entity: type[_EntityT] | None = None
        self._models: dict[str, type[OrmModel]] = {}

    @t.overload
    def __get__(self, instance: None, owner: type[_EntityT]) -> ModelsNamespace[_EntityT]: ...

    @t.overload
    def __get__(self, instance: object, owner: type[_EntityT] | None = None) -> ModelsNamespace[_EntityT]: ...

    def __get__(self, instance: object | None, owner: type[_EntityT] | None = None) -> ModelsNamespace[_EntityT]:
        if owner is None:
            raise AttributeError('models must be accessed through an entity class')
        namespace = type(self)()
        namespace._entity = owner
        namespace._models = self._models.setdefault(owner, {})
        return namespace

    @t.overload
    def __getattr__(self, name: t.Literal['read']) -> type[OrmModel]: ...

    @t.overload
    def __getattr__(self, name: t.Literal['create']) -> type[OrmModel]: ...

    @t.overload
    def __getattr__(self, name: t.Literal['update']) -> type[OrmModel]: ...

    @t.overload
    def __getattr__(self, name: str) -> type[OrmModel]: ...

    def __getattr__(self, name: str) -> type[OrmModel]:
        if name.startswith('_'):
            raise AttributeError(name)
        if name not in self._models:
            if name not in self._names:
                models = ', '.join(sorted(self._names))
                raise UnsupportedModelError(f"'{name}' model is not supported; valid projections: {models}")
            if self._entity is None:
                raise RuntimeError('model namespace is not bound to an entity class')
            self._models[name] = self._build_model(name)
        return self._models[name]

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | sorted(self._names))

    def _build_model(self, name: str) -> type[OrmModel]:
        fields: dict[str, tuple[t.Any, t.Any]] = {}
        for field_name, orm_field in iter_fields(self._entity).items():
            spec = orm_field.spec
            if name == 'create' and spec.readonly:
                continue
            if name == 'update' and (spec.readonly or orm_field.fset is None):
                continue
            default = ... if spec.required else spec.default
            field_info = pdt.Field(
                default,
                description=spec.description,
                examples=[spec.example] if spec.example is not None else None,
                alias=spec.backend_key if spec.backend_key != field_name else None,  # TODO shift None to backend key
                json_schema_extra={
                    'readOnly': spec.readonly,
                },
            )
            fields[field_name] = (spec.value_type, field_info)
        return pdt.create_model(
            f'{self._entity.__name__}{name.capitalize()}Model',
            __base__=OrmModel,
            **fields,
        )
