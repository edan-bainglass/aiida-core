from __future__ import annotations

from entity import Entity
from fields import ModelField, field

from aiida.manage.manager import get_manager
from aiida.orm.implementation import BackendUser, StorageBackend


class User(Entity[BackendUser]):
    def __init__(
        self,
        email: str,
        first_name: str = '',
        last_name: str = '',
        institution: str = '',
        backend: StorageBackend | None = None,
        **kwargs,
    ):
        backend = backend or get_manager().get_profile_storage()
        backend_entity = backend.users.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            institution=institution,
        )
        super().__init__(backend_entity, **kwargs)

    @field
    def email(self) -> str:
        """The email of the user."""
        return self._backend_entity.email

    @field(model_field_info=ModelField(''))
    def first_name(self) -> str:
        """The first name of the user."""
        return self._backend_entity.first_name

    @field(model_field_info=ModelField(''))
    def last_name(self) -> str:
        """The last name of the user."""
        return self._backend_entity.last_name

    @field(model_field_info=ModelField(''))
    def institution(self) -> str:
        """The institution of the user."""
        return self._backend_entity.institution
