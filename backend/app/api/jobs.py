from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.database import get_db
from app.models import Job, Queue, ScheduledJob
from app.schemas import JobCreate, JobResponse, JobListResponse
from app.core.dependencies import get_current_user
from app.models import User
from uuid import uuid4
from datetime import datetime, timedelta
from croniter import croniter
import json
from typing import Optional

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate queue exists
    result = await db.execute(select(Queue).where(Queue.id == job_data.queue_id))
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    # If idempotency key provided, check if job already exists
    if job_data.idempotency_key:
        result = await db.execute(
            select(Job).where(Job.idempotency_key == job_data.idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing  # Return existing job (idempotent)

    # Determine scheduled_at
    scheduled_at = None
    job_type = job_data.job_type

    if job_type == "immediate":
        scheduled_at = datetime.utcnow()  # will be picked up immediately
    elif job_type == "delayed":
        if not job_data.delay_seconds:
            raise HTTPException(status_code=400, detail="delay_seconds required for delayed jobs")
        scheduled_at = datetime.utcnow() + timedelta(seconds=job_data.delay_seconds)
    elif job_type == "scheduled":
        if not job_data.scheduled_at:
            raise HTTPException(status_code=400, detail="scheduled_at required for scheduled jobs")
        scheduled_at = job_data.scheduled_at
    elif job_type == "cron":
        if not job_data.cron_expression:
            raise HTTPException(status_code=400, detail="cron_expression required for cron jobs")
        if not croniter.is_valid(job_data.cron_expression):
            raise HTTPException(status_code=400, detail="Invalid cron expression")
        scheduled_at = croniter(job_data.cron_expression).get_next(datetime)
    elif job_type == "batch":
        if not job_data.batch_count or job_data.batch_count < 1:
            raise HTTPException(status_code=400, detail="batch_count must be >= 1")
        # We'll create multiple jobs below
    else:
        raise HTTPException(status_code=400, detail="Invalid job_type")

    # Base job attributes
    job_attrs = {
        "name": job_data.name,
        "queue_id": job_data.queue_id,
        "target": job_data.target,
        "payload": job_data.payload or {},
        "job_type": job_type,
        "max_retries": job_data.max_retries or queue.max_retries,
        "retry_strategy": job_data.retry_strategy or queue.default_retry_strategy,
        "retry_config": job_data.retry_config or {},
        "idempotency_key": job_data.idempotency_key,
    }

    if job_type == "batch":
        # Create multiple jobs
        jobs = []
        for _ in range(job_data.batch_count):
            new_job = Job(
                id=str(uuid4()),
                **job_attrs,
                status="queued",
                scheduled_at=datetime.utcnow()  # immediate execution
            )
            db.add(new_job)
            jobs.append(new_job)
        await db.commit()
        # Return first job as representative (or could return list, but we stick to response_model)
        return jobs[0]
    else:
        # Single job
        new_job = Job(
            id=str(uuid4()),
            **job_attrs,
            status="queued" if job_type == "immediate" else "scheduled",
            scheduled_at=scheduled_at,
        )
        db.add(new_job)

        # If cron, also create ScheduledJob entry
        if job_type == "cron":
            scheduled_entry = ScheduledJob(
                id=str(uuid4()),
                job_id=new_job.id,
                cron_expression=job_data.cron_expression,
                next_run_at=scheduled_at
            )
            db.add(scheduled_entry)

        await db.commit()
        await db.refresh(new_job)
        return new_job

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    queue_id: Optional[str] = None,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Job)
    if queue_id:
        query = query.where(Job.queue_id == queue_id)
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)

    # Count total
    count_query = select(func.count()).select_from(Job)
    if queue_id:
        count_query = count_query.where(Job.queue_id == queue_id)
    if status:
        count_query = count_query.where(Job.status == status)
    if job_type:
        count_query = count_query.where(Job.job_type == job_type)
    total = await db.scalar(count_query) or 0

    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Job.created_at.desc())
    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        items=jobs,
        total=total,
        page=page,
        limit=limit
    )

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Only allow deletion if not running or completed?
    # We'll allow deletion for any status except 'running' and 'claimed'
    if job.status in ["running", "claimed"]:
        raise HTTPException(status_code=400, detail="Cannot delete a running or claimed job")
    await db.delete(job)
    await db.commit()
    return None

@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ["failed", "dead_letter"]:
        raise HTTPException(status_code=400, detail="Only failed or dead_letter jobs can be retried")
    job.status = "queued"
    job.retry_count = 0
    job.error_message = None
    job.scheduled_at = datetime.utcnow()
    await db.commit()
    return {"message": "Job queued for retry"}