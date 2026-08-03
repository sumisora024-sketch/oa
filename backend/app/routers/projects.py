from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import Employee, Project, ProjectAssignment, User
from app.schemas import AssignmentCreate, AssignmentOut, AssignmentUpdate, CandidateScore, EmailAnalyzeIn, ProjectCreate, ProjectOut, ProjectUpdate
from app.services.ai import build_recommendation_prompt, extract_project_metadata, score_candidates
from app.services.mailbox import poll_mailbox_once
from app.services.salary import refresh_salary_record_for_employee

router = APIRouter(prefix="/projects", tags=["projects"])


def parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


ASSIGNMENT_STATUSES = {"assigned", "unassigned"}


def active_assignment_count(db: Session, project_id: int, exclude_assignment_id: int | None = None) -> int:
    stmt = select(ProjectAssignment.id).where(
        ProjectAssignment.project_id == project_id,
        ProjectAssignment.status == "assigned",
    )
    if exclude_assignment_id is not None:
        stmt = stmt.where(ProjectAssignment.id != exclude_assignment_id)
    return len(
        list(
            db.scalars(
                stmt
            ).all()
        )
    )


def ensure_assignment_status(value: str) -> None:
    if value not in ASSIGNMENT_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的归属状态")


def ensure_project_capacity(db: Session, project: Project, exclude_assignment_id: int | None = None) -> None:
    if project.headcount is not None and active_assignment_count(db, project.id, exclude_assignment_id) >= project.headcount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已达到项目所需人数，不能继续归属")


def assignment_out(assignment: ProjectAssignment) -> dict:
    return {
        "id": assignment.id,
        "project_id": assignment.project_id,
        "employee_id": assignment.employee_id,
        "employee_name": assignment.employee.full_name if assignment.employee else str(assignment.employee_id),
        "role": assignment.role,
        "status": assignment.status,
        "created_at": assignment.created_at,
    }


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role in {"admin", "pm"}:
        return list(db.scalars(select(Project).order_by(Project.created_at.desc())).all())
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/analyze-email", response_model=ProjectOut)
async def analyze_email(payload: EmailAnalyzeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    metadata = await extract_project_metadata(payload.subject, payload.body, payload.attachment_text)
    project = Project(
        client_company=metadata["client_company"],
        project_name=metadata["project_name"],
        description=metadata["description"],
        required_skills=metadata["required_skills"],
        workplace=metadata["workplace"],
        nationality_requirement=metadata.get("nationality_requirement"),
        duration=metadata.get("duration"),
        start_date=parse_optional_date(metadata.get("start_date")),
        end_date=parse_optional_date(metadata.get("end_date")),
        headcount=metadata.get("headcount"),
        unit_price=metadata.get("unit_price"),
        source_email_subject=payload.subject,
        raw_email=payload.body,
        attachment_name="mail-attachment-text" if payload.attachment_text else None,
        attributes=metadata.get("attributes"),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/mailbox/poll")
async def poll_mailbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    return await poll_mailbox_once()


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    assignments = list(db.scalars(select(ProjectAssignment).order_by(ProjectAssignment.created_at.desc())).all())
    return [assignment_out(assignment) for assignment in assignments]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件不存在")
    if user.role in {"admin", "pm"}:
        return project
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件不存在")
    if payload.headcount is not None and payload.headcount < active_assignment_count(db, project_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所需人数不能小于当前归属人数")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件不存在")
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/assignments", response_model=AssignmentOut)
def assign_employee(project_id: int, payload: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    ensure_assignment_status(payload.status)
    project = db.get(Project, project_id)
    employee = db.get(Employee, payload.employee_id)
    if not project or not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件或人员不存在")
    existing = db.scalar(select(ProjectAssignment).where(ProjectAssignment.project_id == project_id, ProjectAssignment.employee_id == payload.employee_id))
    if existing:
        if payload.status == "assigned":
            ensure_project_capacity(db, project, existing.id)
        existing.role = payload.role
        existing.status = payload.status
        assignment = existing
    else:
        if payload.status == "assigned":
            ensure_project_capacity(db, project)
        assignment = ProjectAssignment(project_id=project_id, employee_id=payload.employee_id, role=payload.role, status=payload.status)
        db.add(assignment)
    db.flush()
    refresh_salary_record_for_employee(db, payload.employee_id)
    db.commit()
    db.refresh(assignment)
    return assignment_out(assignment)


@router.put("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(assignment_id: int, payload: AssignmentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    assignment = db.get(ProjectAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="归属记录不存在")

    updates = payload.model_dump(exclude_unset=True)
    target_project_id = updates.get("project_id", assignment.project_id)
    target_employee_id = updates.get("employee_id", assignment.employee_id)
    target_status = updates.get("status", assignment.status)
    ensure_assignment_status(target_status)

    project = db.get(Project, target_project_id)
    employee = db.get(Employee, target_employee_id)
    if not project or not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件或人员不存在")
    if target_status == "assigned":
        ensure_project_capacity(db, project, assignment.id)

    old_employee_id = assignment.employee_id
    assignment.project_id = target_project_id
    assignment.employee_id = target_employee_id
    if "role" in updates:
        assignment.role = updates["role"]
    assignment.status = target_status
    db.flush()
    refresh_salary_record_for_employee(db, old_employee_id)
    if target_employee_id != old_employee_id:
        refresh_salary_record_for_employee(db, target_employee_id)
    db.commit()
    db.refresh(assignment)
    return assignment_out(assignment)


@router.delete("/assignments/{assignment_id}", response_model=AssignmentOut)
def unassign_employee(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    assignment = db.get(ProjectAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="归属记录不存在")
    assignment.status = "unassigned"
    db.flush()
    refresh_salary_record_for_employee(db, assignment.employee_id)
    db.commit()
    db.refresh(assignment)
    return assignment_out(assignment)


@router.get("/{project_id}/recommendations", response_model=list[CandidateScore])
def recommend(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "pm"})
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件不存在")
    employees = list(db.scalars(select(Employee).where(Employee.is_deleted.is_(False))).all())
    cache.set_json(
        f"candidate_pool:{project_id}",
        {"project_id": project_id, "employees": [employee.id for employee in employees], "prompt": build_recommendation_prompt(project, employees)},
        900,
    )
    return score_candidates(project, employees)
