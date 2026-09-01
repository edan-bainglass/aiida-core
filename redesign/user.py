from __future__ import annotations

from entity import Entity
from fields import ModelFieldInfo, field

from aiida import orm
from aiida.common import exceptions
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

    def __str__(self) -> str:
        return self.email

    def __eq__(self, other) -> bool:
        if not isinstance(other, User):
            return False

        return self.email == other.email

    @field
    def email(self) -> str:
        """The email of the user."""
        return self._backend_entity.email

    @email.setter  # type: ignore[no-redef]
    def email(self, email: str) -> None:
        self._backend_entity.email = email

    @field(model_field_info=ModelFieldInfo(default=''))
    def first_name(self) -> str:
        """The first name of the user."""
        return self._backend_entity.first_name

    @first_name.setter  # type: ignore[no-redef]
    def first_name(self, first_name: str) -> None:
        self._backend_entity.first_name = first_name

    @field(model_field_info=ModelFieldInfo(default=''))
    def last_name(self) -> str:
        """The last name of the user."""
        return self._backend_entity.last_name

    @last_name.setter  # type: ignore[no-redef]
    def last_name(self, last_name: str) -> None:
        self._backend_entity.last_name = last_name

    @field(model_field_info=ModelFieldInfo(default=''))
    def institution(self) -> str:
        """The institution of the user."""
        return self._backend_entity.institution

    @institution.setter  # type: ignore[no-redef]
    def institution(self, institution: str) -> None:
        self._backend_entity.institution = institution

    @property
    def is_default(self) -> bool:
        """Return whether the user is the default user."""
        default_user = orm.User.collection.get_default()
        return default_user is not None and self.pk == default_user.pk

    @property
    def full_name(self) -> str:
        """Return the user full name (if available) and email."""
        if self.first_name and self.last_name:
            full_name = f'{self.first_name} {self.last_name} ({self.email})'
        elif self.first_name:
            full_name = f'{self.first_name} ({self.email})'
        elif self.last_name:
            full_name = f'{self.last_name} ({self.email})'
        else:
            full_name = f'{self.email}'

        return full_name

    @classmethod
    def get_one(cls, identifier: int | str) -> User | None:
        """Get a user by identifier (PK or email)."""
        key = 'pk' if isinstance(identifier, int) else 'email'
        try:
            return orm.User.collection.get(**{key: identifier})  # type: ignore[return-value]
        except exceptions.NotExistent:
            return None

    @staticmethod
    def normalize_email(email: str) -> str:
        """Normalize the address by lowercasing the domain part of the email address (taken from Django)."""
        email = email or ''
        try:
            email_name, domain_part = email.strip().rsplit('@', 1)
        except ValueError:
            pass
        else:
            email = f'{email_name}@{domain_part.lower()}'
        return email
