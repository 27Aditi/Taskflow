import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

import models
import schemas
from database import engine, get_db, Base
from auth import hash_password, verify_password, create_access_token, get_current_user

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TaskFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def board_or_404(board_id: int, db: Session) -> models.Board:
    board = db.query(models.Board).filter(models.Board.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


def ensure_board_access(board: models.Board, user: models.User, db: Session):
    if board.owner_id == user.id:
        return
    membership = (
        db.query(models.BoardMember)
        .filter(models.BoardMember.board_id == board.id, models.BoardMember.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="You do not have access to this board")


@app.post("/api/auth/signup", response_model=schemas.Token, status_code=201)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(models.User)
        .filter(or_(models.User.email == payload.email, models.User.username == payload.username))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "user": user}


@app.post("/api/auth/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "user": user}


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/api/boards", response_model=list[schemas.BoardOut])
def list_boards(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    owned = db.query(models.Board).filter(models.Board.owner_id == current_user.id)
    member_board_ids = [
        m.board_id
        for m in db.query(models.BoardMember).filter(models.BoardMember.user_id == current_user.id).all()
    ]
    member_boards = db.query(models.Board).filter(models.Board.id.in_(member_board_ids))
    boards = {b.id: b for b in list(owned) + list(member_boards)}
    return list(boards.values())


@app.post("/api/boards", response_model=schemas.BoardOut, status_code=201)
def create_board(
    payload: schemas.BoardCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = models.Board(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


@app.get("/api/boards/{board_id}", response_model=schemas.BoardOut)
def get_board(
    board_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = board_or_404(board_id, db)
    ensure_board_access(board, current_user, db)
    return board


@app.delete("/api/boards/{board_id}", status_code=204)
def delete_board(
    board_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = board_or_404(board_id, db)
    if board.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the board owner can delete this board")
    db.delete(board)
    db.commit()
    return None


@app.get("/api/boards/{board_id}/members", response_model=list[schemas.MemberOut])
def list_members(
    board_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = board_or_404(board_id, db)
    ensure_board_access(board, current_user, db)
    return board.members


@app.post("/api/boards/{board_id}/members", response_model=schemas.MemberOut, status_code=201)
def add_member(
    board_id: int,
    payload: schemas.MemberAdd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = board_or_404(board_id, db)
    if board.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the board owner can add members")

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found with that email")

    existing = (
        db.query(models.BoardMember)
        .filter(models.BoardMember.board_id == board_id, models.BoardMember.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this board")

    member = models.BoardMember(board_id=board_id, user_id=user.id, role=models.RoleEnum.member)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@app.get("/api/boards/{board_id}/tasks", response_model=list[schemas.TaskOut])
def list_tasks(
    board_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = board_or_404(board_id, db)
    ensure_board_access(board, current_user, db)
    return db.query(models.Task).filter(models.Task.board_id == board_id).all()


@app.post("/api/boards/{board_id}/tasks", response_model=schemas.TaskOut, status_code=201)
def create_task(
    board_id: int,
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    board = board_or_404(board_id, db)
    ensure_board_access(board, current_user, db)

    task = models.Task(
        board_id=board_id,
        title=payload.title,
        description=payload.description,
        assigned_to=payload.assigned_to,
        status=payload.status,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    board = board_or_404(task.board_id, db)
    ensure_board_access(board, current_user, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    board = board_or_404(task.board_id, db)
    ensure_board_access(board, current_user, db)

    db.delete(task)
    db.commit()
    return None


static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(static_dir, "index.html"))
