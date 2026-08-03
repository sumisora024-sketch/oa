import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.init_db import init_db
from app.routers import ai_assistant, attendance, approvals, auth, contracts, documents, employees, external, external_personnel, homepage, mail_settings, offboarding, projects, reimbursements, subcontracting, ui_permissions
from app.services.audit import audit_mutation_request
from app.services.contract_reminders import contract_reminder_loop
from app.services.idempotency import reject_duplicate_mutation
from app.services.mailbox import mailbox_listener_loop
from app.services.offboarding import offboarding_loop


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(audit_mutation_request)
app.middleware("http")(reject_duplicate_mutation)


async def init_db_with_retry(retries: int = 30, delay_seconds: int = 2) -> None:
    for attempt in range(1, retries + 1):
        try:
            init_db()
            return
        except Exception as exc:
            if attempt == retries:
                raise
            print(f"[startup] database not ready ({attempt}/{retries}): {exc}")
            await asyncio.sleep(delay_seconds)


@app.on_event("startup")
async def startup() -> None:
    await init_db_with_retry()
    app.state.mailbox_task = asyncio.create_task(mailbox_listener_loop())
    app.state.contract_reminder_task = asyncio.create_task(contract_reminder_loop())
    app.state.offboarding_task = asyncio.create_task(offboarding_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "mailbox_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    contract_task = getattr(app.state, "contract_reminder_task", None)
    if contract_task:
        contract_task.cancel()
        try:
            await contract_task
        except asyncio.CancelledError:
            pass
    offboarding_task = getattr(app.state, "offboarding_task", None)
    if offboarding_task:
        offboarding_task.cancel()
        try:
            await offboarding_task
        except asyncio.CancelledError:
            pass


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}


app.include_router(auth.router, prefix="/api")
app.include_router(homepage.router, prefix="/api")
app.include_router(ai_assistant.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(offboarding.router, prefix="/api")
app.include_router(contracts.router, prefix="/api")
app.include_router(external.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(reimbursements.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(subcontracting.router, prefix="/api")
app.include_router(external_personnel.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(mail_settings.router, prefix="/api")
app.include_router(ui_permissions.router, prefix="/api")
