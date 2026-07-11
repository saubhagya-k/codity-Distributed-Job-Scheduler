from pydantic import BaseModel, EmailStr, Field

from typing import Optional, List, Any, Union
from datetime import datetime
from uuid import UUID

# ----- Auth -----
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ----- Projects -----
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    org_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ----- Queues -----
class QueueCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: UUID 
    priority: int = 0
    concurrency_limit: int = 5
    max_retries: int = 3
    default_retry_strategy: str = "fixed"  # fixed, linear, exponential

class QueueUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    concurrency_limit: Optional[int] = None
    max_retries: Optional[int] = None
    default_retry_strategy: Optional[str] = None
    is_paused: Optional[bool] = None

class QueueResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    project_id: UUID
    priority: int
    concurrency_limit: int
    max_retries: int
    default_retry_strategy: str
    is_paused: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True




class JobCreate(BaseModel):
    name: str
    queue_id: UUID
    target: str                     # URL or function reference
    payload: Optional[dict] = {}
    job_type: str = "immediate"     # immediate, delayed, scheduled, cron, batch
    scheduled_at: Optional[datetime] = None
    delay_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    max_retries: Optional[int] = None
    retry_strategy: Optional[str] = None  # fixed, linear, exponential
    retry_config: Optional[dict] = {}
    idempotency_key: Optional[str] = None

    # For batch jobs
    batch_count: Optional[int] = 1

class JobResponse(BaseModel):
    id: UUID
    name: str
    queue_id: UUID
    job_type: str
    status: str
    target: str
    payload: dict
    scheduled_at: Optional[datetime]
    retry_count: int
    max_retries: int
    retry_strategy: str
    retry_config: dict
    claimed_by: Optional[UUID]
    claimed_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    idempotency_key: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    limit: int