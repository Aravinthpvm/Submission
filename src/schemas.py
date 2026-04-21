from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


VALID_ROLES = {
    "student",
    "trainer",
    "institution",
    "programme_manager",
    "monitoring_officer",
}


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal[
        "student",
        "trainer",
        "institution",
        "programme_manager",
        "monitoring_officer",
    ]
    institution_id: int | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MonitoringTokenRequest(BaseModel):
    key: str


class BatchCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    institution_id: int


class BatchJoinRequest(BaseModel):
    token: str


class SessionCreateRequest(BaseModel):
    batch_id: int
    title: str = Field(min_length=2, max_length=255)
    date: date
    start_time: time
    end_time: time


class AttendanceMarkRequest(BaseModel):
    session_id: int
    status: Literal["present", "absent", "late"]


class AttendanceView(BaseModel):
    student_id: int
    student_name: str
    status: str
    marked_at: datetime


class MessageResponse(BaseModel):
    message: str
