from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID


class UserBase(BaseModel):
    username: str = Field(min_length =1, max_length =50)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length =8 , max_length = 72)

    @field_validator("password")
    @classmethod
    def password_must_be_within_bcrypt_byte_limit(cls, v: str) -> str:
        # bcrypt silently truncates anything past 72 bytes (not chars).
        # Multi-byte UTF-8 chars can blow past 72 bytes even with <72 chars.
        if len(v.encode("utf-8")) > 72:
            raise ValueError(
                "Password is too long (max 72 bytes when UTF-8 encoded)."
            )
        return v


class UserResponse(UserBase):
    id: UUID

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str
