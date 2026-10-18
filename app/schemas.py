from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class Signup(Login):
    name: Text


class ClassInput(Input):
    name: Text
    dateTime: datetime
    instructor: Text
    availableSlots: Annotated[int, Field(strict=True, ge=1, le=10000)]

    @field_validator('dateTime')
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('dateTime must include a timezone offset')
        return value


class BookingInput(Input):
    class_id: Annotated[int, Field(strict=True, gt=0)]
    client_name: Text
    client_email: EmailStr


class RefreshInput(Input):
    refresh_token: Annotated[str, Field(min_length=1, max_length=200)]
