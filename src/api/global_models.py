from pydantic import BaseModel, Field
from typing import Union, Optional

class UserIcon(BaseModel):
    type: int = Field(
        ge=0,
        le=1
    )
    data: Union[str, int] = Field(
        min_length=1,
        max_length=255
    )

class AuthorMasquerade(BaseModel):
    username: Optional[str] = Field(
        min_length=1,
        max_length=20
    )
    icon: UserIcon = None
