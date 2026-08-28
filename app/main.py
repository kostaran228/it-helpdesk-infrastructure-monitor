import shutil
import subprocess
from uuid import uuid4
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .auth import authenticate_user, create_access_token, get_current_it_operator, get_current_specialist, get_current_system_admin, get_current_user, initialize_system_admin, register_employee
from .database import Base, engine, get_db
from .models import Asset, AssetAvailability, Ticket, TicketStatus, User, UserRole
from .schemas import AssetCreate, AssetRead, LoginRequest, LoginResponse, ProfileRead, ProfileUpdate, RegisterRequest, TicketCreate, TicketRead, TicketStatusUpdate, UserRead, UserRoleUpdate

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="IT HelpDesk & Infrastructure Monitor",
    version="0.1.0",
    description="API для учёта заявок в IT-поддержку.",
    docs_url=None,
    redoc_url=None,
)
STATIC_DIR = Path(__file__).parent / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def login_response(user: User) -> LoginResponse:
    return LoginResponse(
        access_token=create_access_token(user.email, user.role),
        specialist_email=user.email,
        user_role=user.role,
        full_name=user.full_name or user.email.split("@", 1)[0],
        avatar_path=user.avatar_path,
    )


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/docs", include_in_schema=False)
def user_docs_redirect():
    return RedirectResponse("/")


@app.get("/api-docs", include_in_schema=False)
def technical_docs():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="Техническая документация API")


@app.get("/health")
def healthcheck(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    return login_response(user)


@app.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    return {"needs_setup": db.scalar(select(User).where(User.role == UserRole.system_admin)) is None}


@app.post("/setup/initialize", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def initialize_owner(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = initialize_system_admin(db, payload.email, payload.password, payload.full_name)
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Системный владелец уже настроен")
    return login_response(user)


@app.post("/auth/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = register_employee(db, payload.email, payload.password, payload.full_name)
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Аккаунт с таким email уже существует")
    return login_response(user)


@app.get("/auth/me", response_model=ProfileRead)
def current_profile(user: User = Depends(get_current_user)):
    return user


@app.patch("/auth/profile", response_model=ProfileRead)
def update_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/profile/avatar", response_model=ProfileRead)
def upload_avatar(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed_types = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Подойдут изображения JPG, PNG или WEBP")
    suffix = allowed_types[file.content_type]
    file_name = f"avatar-{user.id}-{uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / file_name
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output, length=1024 * 1024)
    if destination.stat().st_size > 5 * 1024 * 1024:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Размер изображения не должен превышать 5 МБ")
    if user.avatar_path:
        (STATIC_DIR / user.avatar_path.removeprefix("/static/")).unlink(missing_ok=True)
    user.avatar_path = f"/static/uploads/{file_name}"
    db.commit()
    db.refresh(user)
    return user


@app.get("/admin/users", response_model=list[UserRead])
def list_users(_: User = Depends(get_current_system_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@app.patch("/admin/users/{user_id}/role", response_model=UserRead)
def update_user_role(user_id: int, payload: UserRoleUpdate, _: User = Depends(get_current_system_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if payload.role not in {UserRole.employee, UserRole.developer}:
        raise HTTPException(status_code=400, detail="Можно выдать только статус разработчика или сотрудника")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@app.post("/tickets", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(**payload.model_dump())
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.get("/tickets", response_model=list[TicketRead])
def list_tickets(db: Session = Depends(get_db)):
    return db.scalars(select(Ticket).order_by(Ticket.created_at.desc())).all()


@app.patch("/tickets/{ticket_id}/status", response_model=TicketRead)
def update_ticket_status(ticket_id: int, payload: TicketStatusUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_specialist)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    ticket.status = payload.status
    db.commit()
    db.refresh(ticket)
    return ticket


@app.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(Asset).where(Asset.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Устройство с таким именем уже существует")
    asset = Asset(**payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@app.get("/assets", response_model=list[AssetRead])
def list_assets(db: Session = Depends(get_db)):
    return db.scalars(select(Asset).order_by(Asset.created_at.desc())).all()


@app.post("/assets/{asset_id}/check", response_model=AssetRead)
def check_asset_availability(asset_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_it_operator)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Устройство не найдено")
    if not asset.ip_address:
        raise HTTPException(status_code=400, detail="Для устройства не указан IP-адрес")

    check = subprocess.run(
        ["ping", "-c", "1", "-W", "1", asset.ip_address],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    asset.availability = AssetAvailability.online if check.returncode == 0 else AssetAvailability.offline
    asset.last_checked_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)
    return asset
