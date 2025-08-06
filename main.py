import shutil
import os
from typing import List
from fastapi import FastAPI, Form, Request, Depends, HTTPException, UploadFile, File, status, WebSocket, \
    WebSocketDisconnect
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, Field, validator, ValidationError, field_validator
from fastapi.staticfiles import StaticFiles
from database import SessionLocal, engine
from models import User, Ad, Base
from datetime import datetime
import json

app = FastAPI(title="Mini Project with Swagger and ReDoc Docs")
templates = Jinja2Templates(directory="templates")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
active_connections: List[WebSocket] = []


# --- this is useful ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request):
    return request.cookies.get("user")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


# --- websocket chat ---
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            username = msg_data.get("username", "Анонім")
            message = msg_data.get("message", "")
            now = datetime.now().strftime("%H:%M")

            formatted_message = f"{now} {username}: {message}"

            for connection in active_connections:
                await connection.send_text(formatted_message)
    except WebSocketDisconnect:
        active_connections.remove(websocket)


@app.get("/chat", response_class=HTMLResponse, summary="Chat page")
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


# --- index ---

@app.get("/", response_class=HTMLResponse, summary="Home page with ads")
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    ads = db.query(Ad).all()
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "ads": ads})


# --- auth and User ---
@app.get("/register", response_class=HTMLResponse, summary="Registration form")
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register", summary="Register new user")
async def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    hashed = get_password_hash(password)
    user = User(username=username, password=hashed)
    db.add(user)
    db.commit()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/login", response_class=HTMLResponse, summary="Login form")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", summary="User login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="user", value=user.username, httponly=True)
    return response


@app.get("/logout", summary="Logout user")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("user")
    return response


# --- ads ---

class AdCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100, description="Ad title")
    description: str = Field(..., min_length=10, max_length=1000, description="Ad description")
    price: float = Field(..., gt=0, description="Price must be > 0")
    category: str = Field(..., min_length=2, max_length=50, description="Category")

    @field_validator("title")
    @classmethod
    def no_special_chars(cls, v):
        if any(not (c.isalnum() or c.isspace()) for c in v):
            raise ValueError("Title must not contain special characters")
        return v


@app.get("/ads", response_class=HTMLResponse, summary="Ad creation form")
async def get_ad_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("ads.html", {"request": request, "user": user})


@app.post("/ads", summary="Create new ad")
async def submit_ad(
        request: Request,
        title: str = Form(...),
        description: str = Form(...),
        price: float = Form(...),
        category: str = Form(...),
        photo: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        ad_data = AdCreate(title=title, description=description, price=price, category=category)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    os.makedirs("uploads", exist_ok=True)
    photo_path = os.path.join("uploads", photo.filename)
    with open(photo_path, "wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)

    new_ad = Ad(
        title=ad_data.title,
        description=ad_data.description,
        price=ad_data.price,
        category=ad_data.category,
        photo_filename=photo.filename,
        owner_username=user
    )
    db.add(new_ad)
    db.commit()
    return RedirectResponse(url="/ads", status_code=status.HTTP_302_FOUND)


@app.post("/delete_ad/{ad_id}", summary="Delete ad by owner")
async def delete_ad(ad_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    ad = db.query(Ad).filter(Ad.id == ad_id, Ad.owner_username == user).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found or no permission")
    db.delete(ad)
    db.commit()
    return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)


# --- profile ---

@app.get("/profile", response_class=HTMLResponse, summary="User profile with their ads")
async def profile(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    user_ads = db.query(Ad).filter(Ad.owner_username == user).all()
    return templates.TemplateResponse("prof.html", {"request": request, "user": user, "ads": user_ads})


# --- here's the exception handler--

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {"request": request, "message": exc.detail},
                                      status_code=exc.status_code)
