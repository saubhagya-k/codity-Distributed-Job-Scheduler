from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey,
    Enum, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.database import Base

# -------- Helpers --------
def gen_uuid():
    return str(uuid4())

# -------- Users & Auth --------
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="member")  # admin, member, viewer
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    projects = relationship("Project", back_populates="creator", foreign_keys="Project.created_by")
    organizations = relationship("Organization", back_populates="owner")

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    owner = relationship("User", back_populates="organizations")
    projects = relationship("Project", back_populates="organization")

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="projects")
    creator = relationship("User", back_populates="projects", foreign_keys=[created_by])
    queues = relationship("Queue", back_populates="project")

# -------- Queues --------
class Queue(Base):
    __tablename__ = "queues"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False)
    priority = Column(Integer, default=0)  # lower = higher priority
    concurrency_limit = Column(Integer, default=5)
    max_retries = Column(Integer, default=3)
    default_retry_strategy = Column(String(50), default="fixed")
    is_paused = Column(Boolean, default=False)
    retry_config = Column(JSON, default={})  # { "base_delay": 5, "max_delay": 300, "multiplier": 2.0 }
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="queues")
    jobs = relationship("Job", back_populates="queue", cascade="all, delete-orphan")
    dlq_entries = relationship("DeadLetterQueue", back_populates="queue")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_queue_project_name"),
        Index("ix_queues_project_id", "project_id"),
    )

# -------- Retry Policies (global templates) --------
class RetryPolicy(Base):
    __tablename__ = "retry_policies"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(100), unique=True, nullable=False)
    strategy = Column(String(50), nullable=False)  # fixed, linear, exponential
    base_delay = Column(Integer, nullable=False)   # seconds
    max_delay = Column(Integer, nullable=False)    # seconds
    multiplier = Column(Integer, default=1)        # for exponential
    max_retries = Column(Integer, default=3)

    jobs = relationship("Job", back_populates="retry_policy_ref")

# -------- Jobs --------
class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    queue_id = Column(UUID(as_uuid=False), ForeignKey("queues.id"), nullable=False)
    job_type = Column(String(50), nullable=False)  # immediate, delayed, scheduled, cron, batch
    status = Column(String(50), nullable=False, default="queued")  # queued, scheduled, claimed, running, completed, failed, dead_letter, paused
    payload = Column(JSON, nullable=False, default={})
    target = Column(String(500), nullable=False)   # URL or function reference

    # Worker assignment
    claimed_by = Column(UUID(as_uuid=False), ForeignKey("workers.id"), nullable=True)
    claimed_at = Column(DateTime, nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    retry_strategy = Column(String(50), default="fixed")
    retry_config = Column(JSON, default={})   # overrides queue defaults

    # Scheduling
    scheduled_at = Column(DateTime, nullable=True)   # NULL for immediate

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=True)

    # Workflow dependencies (bonus)
    parent_job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    queue = relationship("Queue", back_populates="jobs")
    worker = relationship("Worker", back_populates="claimed_jobs", foreign_keys=[claimed_by])
    executions = relationship("JobExecution", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")
    retry_policy_ref = relationship("RetryPolicy", back_populates="jobs", foreign_keys="Job.retry_strategy")
    scheduled_entry = relationship("ScheduledJob", back_populates="job", uselist=False, cascade="all, delete-orphan")
    dlq_entry = relationship("DeadLetterQueue", back_populates="job", uselist=False, cascade="all, delete-orphan")
    parent = relationship("Job", remote_side=[id], backref="children")

    __table_args__ = (
        Index("ix_jobs_queue_id_status", "queue_id", "status"),
        Index("ix_jobs_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_jobs_claimed_by", "claimed_by"),
        Index("ix_jobs_idempotency_key", "idempotency_key", unique=True),
    )

# -------- Job Executions --------
class JobExecution(Base):
    __tablename__ = "job_executions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    worker_id = Column(UUID(as_uuid=False), ForeignKey("workers.id"), nullable=False)
    status = Column(String(50), nullable=False)  # started, completed, failed
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)

    job = relationship("Job", back_populates="executions")
    worker = relationship("Worker", back_populates="executions")

    __table_args__ = (
        Index("ix_job_executions_job_id", "job_id"),
        Index("ix_job_executions_worker_id", "worker_id"),
    )

# -------- Job Logs --------
class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    level = Column(String(20), nullable=False)  # info, warning, error, debug
    message = Column(Text, nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, server_default=func.now())

    job = relationship("Job", back_populates="logs")

    __table_args__ = (
        Index("ix_job_logs_job_id_created", "job_id", "created_at"),
    )

# -------- Scheduled Jobs (for cron) --------
class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), unique=True, nullable=False)
    cron_expression = Column(String(100), nullable=False)
    next_run_at = Column(DateTime, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    job = relationship("Job", back_populates="scheduled_entry")

    __table_args__ = (
        Index("ix_scheduled_jobs_next_run_active", "next_run_at", "active"),
    )

# -------- Workers --------
class Worker(Base):
    __tablename__ = "workers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    hostname = Column(String(255), nullable=False)
    pid = Column(String(20), nullable=False)
    status = Column(String(50), nullable=False, default="active")  # active, draining, offline
    last_heartbeat = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    heartbeats = relationship("WorkerHeartbeat", back_populates="worker", cascade="all, delete-orphan")
    claimed_jobs = relationship("Job", back_populates="worker", foreign_keys="Job.claimed_by")
    executions = relationship("JobExecution", back_populates="worker")

    __table_args__ = (
        UniqueConstraint("hostname", "pid", name="uq_worker_hostname_pid"),
        Index("ix_workers_last_heartbeat", "last_heartbeat"),
    )

class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    worker_id = Column(UUID(as_uuid=False), ForeignKey("workers.id"), nullable=False)
    current_jobs_count = Column(Integer, default=0)
    current_job_ids = Column(JSON, default=[])  # list of UUIDs
    sent_at = Column(DateTime, server_default=func.now())

    worker = relationship("Worker", back_populates="heartbeats")

    __table_args__ = (
        Index("ix_worker_heartbeats_worker_id_sent", "worker_id", "sent_at"),
    )

# -------- Dead Letter Queue --------
class DeadLetterQueue(Base):
    __tablename__ = "dead_letter_queue"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    original_job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), unique=True, nullable=False)
    queue_id = Column(UUID(as_uuid=False), ForeignKey("queues.id"), nullable=False)
    job_name = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    retry_history = Column(JSON, default=[])  # list of attempts with timestamps & errors
    failed_at = Column(DateTime, server_default=func.now())
    ai_summary = Column(Text, nullable=True)  # Bonus: AI-generated failure summary

    job = relationship("Job", back_populates="dlq_entry")
    queue = relationship("Queue", back_populates="dlq_entries")

    __table_args__ = (
        Index("ix_dlq_queue_id_failed_at", "queue_id", "failed_at"),
    )