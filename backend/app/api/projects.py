from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Project, User,Organization
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.dependencies import get_current_user
from uuid import uuid4

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project))
    return result.scalars().all()

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find the user's organization
    result = await db.execute(select(Organization).where(Organization.owner_id == current_user.id))
    org = result.scalar_one_or_none()
    if not org:
        # Should not happen because we create one on registration, but just in case
        org = Organization(
            id=str(uuid4()),
            name=f"{current_user.full_name}'s Org",
            owner_id=current_user.id
        )
        db.add(org)
        await db.flush()

    new_project = Project(
        id=str(uuid4()),
        name=project_data.name,
        description=project_data.description,
        org_id=org.id,
        created_by=current_user.id
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project
    # For simplicity, assign to the user's default organization (we'll add org later)
    # We'll set org_id to None for now; we'll refine in Step 4.
    # Temporary: create an organization if none exists, or just allow null.
    # For now, we'll just create a project with a dummy org_id.
    # In production, you'd tie to an existing org.
    # Since we don't have org creation yet, let's create a default org if missing.
    # We'll simplify: let the user pass org_id or we'll create one.
    # For now, we'll use a fixed org_id from the user.
    # We'll improve in Step 4.
    org_id = "00000000-0000-0000-0000-000000000000"  # Placeholder
    # Actually we should create an organization for the user if none exists.
    # For now, let's just use the user's id as org_id to keep it simple.
    new_project = Project(
        id=str(uuid4()),
        name=project_data.name,
        description=project_data.description,
        org_id=current_user.id,  # temporary: user acts as org
        created_by=current_user.id
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project