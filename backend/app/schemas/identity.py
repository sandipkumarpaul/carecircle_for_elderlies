from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.contracts import Contract, Scope


class RegisterInput(Contract):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator('display_name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Name is required')
        return value.strip()


class LoginInput(Contract):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PatientInput(Contract):
    display_name: str = Field(min_length=1, max_length=100)
    timezone: str = 'Asia/Dhaka'
    kind: Literal['self', 'dependent'] = 'self'
    consent: Literal[True]
    consent_basis: str = Field(min_length=10, max_length=300)

    @field_validator('display_name', 'consent_basis')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Value is required')
        return value.strip()

    @field_validator('timezone')
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('Use an IANA timezone') from exc
        return value


class GrantInput(Contract):
    role: Literal['primary', 'secondary']
    scopes: list[Scope] = Field(max_length=21)

    @model_validator(mode='after')
    def role_scopes(self):
        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError('Scopes must be unique')
        management = {Scope.CIRCLE_MANAGE, Scope.PRIVACY_MANAGE}
        if self.role == 'secondary' and management.intersection(self.scopes):
            raise ValueError('Secondary caregivers cannot manage the circle or privacy')
        if self.role == 'primary' and Scope.CIRCLE_MANAGE not in self.scopes:
            raise ValueError('Primary caregivers require circle:manage')
        return self


class InviteInput(GrantInput):
    email: EmailStr
    expires_in_hours: int = Field(default=48, ge=1, le=168)
    consent: Literal[True]


class TokenInput(Contract):
    token: str = Field(min_length=40, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


class AcceptInput(TokenInput):
    consent: Literal[True]
