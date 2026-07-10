from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Queue, Project, User
from app.schemas import QueueCreate, QueueUpdate, QueueResponse
from app.core.dependencies import get_current_user
from uuid import uuid4

router = APIRouter(prefix="/queues", tags=["queues"])

@router.get("/", response_model=list[QueueResponse])
async def list_queues(
    project_id: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Queue)
    if project_id:
        query = query.where(Queue.project_id == project_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=QueueResponse)
async def create_queue(
    queue_data: QueueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == queue_data.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    new_queue = Queue(
        id=str(uuid4()),
        name=queue_data.name,
        description=queue_data.description,
        project_id=queue_data.project_id,
        priority=queue_data.priority,
        concurrency_limit=queue_data.concurrency_limit,
        max_retries=queue_data.max_retries,
        default_retry_strategy=queue_data.default_retry_strategy,
        retry_config={"base_delay": 5, "max_delay": 300, "multiplier": 2.0}
    )
    db.add(new_queue)
    await db.commit()
    await db.refresh(new_queue)
    return new_queue

@router.get("/{queue_id}", response_model=QueueResponse)
async def get_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Queue).where(Queue.id == queue_id))
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue

@router.patch("/{queue_id}", response_model=QueueResponse)
async def update_queue(
    queue_id: str,
    updates: QueueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Queue).where(Queue.id == queue_id))
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    for key, value in updates.dict(exclude_unset=True).items():
        setattr(queue, key, value)
    await db.commit()
    await db.refresh(queue)
    return queue

@router.post("/{queue_id}/pause")
async def pause_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Queue).where(Queue.id == queue_id))
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    queue.is_paused = True
    await db.commit()
    return {"status": "paused"}

@router.post("/{queue_id}/resume")
async def resume_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Queue).where(Queue.id == queue_id))
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    queue.is_paused = False
    await db.commit()
    return {"status": "resumed"}