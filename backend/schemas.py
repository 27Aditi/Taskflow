from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict
from models import RoleEnum, StatusEnum


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class BoardCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class BoardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    owner_id: int
    created_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: RoleEnum
    user: UserOut


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    assigned_to: Optional[int] = None
    status: Optional[StatusEnum] = StatusEnum.todo


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    status: Optional[StatusEnum] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    board_id: int
    title: str
    description: str
    status: StatusEnum
    assigned_to: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: datetime
