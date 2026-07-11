import asyncio
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
import httpx
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.models import Job, Queue, Worker, WorkerHeartbeat, JobExecution, JobLog, DeadLetterQueue
from app.database import AsyncSessionLocal, engine

# Global flag for graceful shutdown
shutdown_flag = False

# Worker identification
hostname = os.uname().nodename if hasattr(os, 'uname') else "unknown"
pid = str(os.getpid())
worker_id = str(uuid.uuid4())   # temporary; will be replaced after registration

async def register_worker():
    """Register or update worker in database and return its ID."""
    global worker_id
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Worker).where(
                Worker.hostname == hostname,
                Worker.pid == pid
            )
        )
        worker = result.scalar_one_or_none()
        if worker:
            worker.last_heartbeat = datetime.utcnow()
            worker.status = "active"
            worker_id = worker.id
            await db.commit()
            return worker_id
        else:
            new_worker = Worker(
                id=worker_id,
                hostname=hostname,
                pid=pid,
                status="active"
            )
            db.add(new_worker)
            await db.commit()
            return worker_id

async def heartbeat_task():
    """Periodically update worker heartbeat."""
    # Register first
    await register_worker()
    while not shutdown_flag:
        async with AsyncSessionLocal() as db:
            # Update heartbeat
            result = await db.execute(select(Worker).where(Worker.id == worker_id))
            worker = result.scalar_one_or_none()
            if worker:
                worker.last_heartbeat = datetime.utcnow()
                # Get currently claimed job IDs
                job_result = await db.execute(
                    select(Job.id).where(Job.claimed_by == worker_id)
                )
                claimed_ids = [str(j[0]) for j in job_result.all()]
                # Create heartbeat record
                hb = WorkerHeartbeat(
                    id=str(uuid.uuid4()),
                    worker_id=worker_id,
                    current_jobs_count=len(claimed_ids),
                    current_job_ids=claimed_ids
                )
                db.add(hb)
                await db.commit()
        await asyncio.sleep(10)

async def execute_job(job_id: str, queue: Queue):
    """Execute a job with its own database session."""
    async with AsyncSessionLocal() as db:
        # Fetch the job again to ensure we have the latest state
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return

        # Mark as claimed
        job.status = "claimed"
        job.claimed_by = worker_id
        job.claimed_at = datetime.utcnow()
        await db.commit()

        # Create execution record
        execution = JobExecution(
            id=str(uuid.uuid4()),
            job_id=job.id,
            worker_id=worker_id,
            status="started",
            started_at=datetime.utcnow()
        )
        db.add(execution)
        await db.commit()

        try:
            # Simulate execution: call target URL
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    job.target,
                    json=job.payload,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code >= 400:
                    raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
            # Success
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            execution.status = "completed"
            execution.exit_code = 0
            execution.output = response.text[:1000] if response else ""
            await db.commit()
            # Add log
            log = JobLog(
                id=str(uuid.uuid4()),
                job_id=job.id,
                level="info",
                message="Job completed successfully"
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            # Failure
            error_msg = str(e)
            job.error_message = error_msg
            job.retry_count += 1
            execution.status = "failed"
            execution.error_stack = error_msg
            execution.exit_code = 1

            # Determine if we should retry
            if job.retry_count < job.max_retries:
                job.status = "scheduled"
                # Calculate delay based on retry strategy
                retry_strategy = job.retry_strategy or queue.default_retry_strategy
                retry_config = job.retry_config or queue.retry_config or {}
                base_delay = retry_config.get("base_delay", 5)
                max_delay = retry_config.get("max_delay", 300)
                multiplier = retry_config.get("multiplier", 2.0)

                if retry_strategy == "fixed":
                    delay = base_delay
                elif retry_strategy == "linear":
                    delay = base_delay * (job.retry_count + 1)
                elif retry_strategy == "exponential":
                    delay = min(base_delay * (multiplier ** job.retry_count), max_delay)
                else:
                    delay = base_delay

                job.scheduled_at = datetime.utcnow() + timedelta(seconds=delay)
                # Log retry
                log = JobLog(
                    id=str(uuid.uuid4()),
                    job_id=job.id,
                    level="warning",
                    message=f"Job failed, retry {job.retry_count}/{job.max_retries} scheduled in {delay}s",
                    meta_data={"error": error_msg}
                )
                db.add(log)
            else:
                # Move to DLQ
                job.status = "dead_letter"
                dlq = DeadLetterQueue(
                    id=str(uuid.uuid4()),
                    original_job_id=job.id,
                    queue_id=job.queue_id,
                    job_name=job.name,
                    payload=job.payload,
                    error_message=error_msg,
                    stack_trace=error_msg,
                    retry_history=[{"attempt": job.retry_count, "error": error_msg}]
                )
                db.add(dlq)
                log = JobLog(
                    id=str(uuid.uuid4()),
                    job_id=job.id,
                    level="error",
                    message=f"Job moved to Dead Letter Queue after {job.retry_count} retries"
                )
                db.add(log)
            await db.commit()

async def claim_and_execute():
    """Main loop: claim and execute jobs."""
    while not shutdown_flag:
        async with AsyncSessionLocal() as db:
            # Get all active queues with pending jobs
            queues_result = await db.execute(
                select(Queue).where(
                    Queue.is_paused == False
                ).order_by(Queue.priority.asc())
            )
            queues = queues_result.scalars().all()

            for queue in queues:
                # Count how many jobs this worker currently has claimed for this queue
                claimed_count_result = await db.execute(
                    select(func.count(Job.id)).where(
                        Job.queue_id == queue.id,
                        Job.claimed_by == worker_id,
                        Job.status.in_(["claimed", "running"])
                    )
                )
                claimed_count = claimed_count_result.scalar() or 0
                available = queue.concurrency_limit - claimed_count
                if available <= 0:
                    continue

                # Fetch eligible jobs
                now = datetime.utcnow()
                jobs_result = await db.execute(
                    select(Job).where(
                        Job.queue_id == queue.id,
                        or_(
                            Job.status == "queued",
                            and_(Job.status == "scheduled", Job.scheduled_at <= now)
                        ),
                        Job.claimed_by.is_(None)
                    )
                    .order_by(Job.created_at.asc())
                    .limit(available)
                    .with_for_update(skip_locked=True)
                )
                jobs = jobs_result.scalars().all()

                for job in jobs:
                    # Spawn separate task for each job with its own session
                    asyncio.create_task(execute_job(job.id, queue))

        await asyncio.sleep(1)

def signal_handler(sig, frame):
    global shutdown_flag
    print(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_flag = True

async def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Register worker
    await register_worker()
    print(f"Worker {worker_id} registered on {hostname}:{pid}")

    # Start heartbeat task
    heartbeat = asyncio.create_task(heartbeat_task())

    # Start main loop
    try:
        await claim_and_execute()
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass
        print("Worker shut down gracefully.")

if __name__ == "__main__":
    asyncio.run(main())