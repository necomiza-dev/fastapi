import json
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm
import jwt

from models import Movietop

app = FastAPI()

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Загружаем фильмы из movies.json
with open("movies.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    movies: List[dict] = data["movies"]

movietop_instances: List[Movietop] = [
    Movietop(name=movie["name"], id=movie["id"], cost=movie["cost"], director=movie["director"])
    for movie in movies
]

university = {
    "name": "Брянский государственный инженерно-технологический университет",
    "address": "Брянск, Станке-Димитрова д.3"
}

# JWT настройки
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10

VALID_USER = "admin"
VALID_PASSWORD = "admin"

# Функция для создания токена
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Функция для получения текущего пользователя из токена (теперь читаем из куки)
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    return username

@app.get("/study", response_class=HTMLResponse)
async def study(request: Request):
    return templates.TemplateResponse("studu.html", {"request": request, "university": university})

@app.get("/movietop", response_class=HTMLResponse)
async def movietop(request: Request):
    # Добавляем описание из файла для каждого фильма
    for movie in movies:
        description_path = movie.get("description_path")
        if description_path and os.path.exists(description_path[1:]):  # Убираем /static
            with open(description_path[1:], "r", encoding="utf-8") as f:
                movie["description"] = f.read()
        else:
            movie["description"] = "Описание отсутствует"
    return templates.TemplateResponse("movietop.html", {"request": request, "movies": movies})

@app.get("/movietop/{movie_name}", response_class=JSONResponse)
async def get_movie(movie_name: str):
    for movie in movies:
        if movie["name_en"].lower() == movie_name.lower():
            return movie
    raise HTTPException(status_code=404, detail="Фильм не найден")

@app.get("/add_movie", response_class=HTMLResponse)
async def add_movie_form(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("add_movie.html", {"request": request})

@app.post("/add_movie")
async def add_movie(
        name: str = Form(...),
        name_en: str = Form(...),
        director: str = Form(...),
        cost: int = Form(...),
        year: int = Form(...),
        is_classic_str: Optional[str] = Form(None),
        description_file: UploadFile = File(...),
        cover_file: UploadFile = File(...),
        current_user: str = Depends(get_current_user)
):
    is_classic = is_classic_str == "true"
    new_id = max(movie["id"] for movie in movies) + 1

    cover_path = f"/static/covers/{new_id}_poster.jpg"
    with open(f"static/covers/{new_id}_poster.jpg", "wb") as f:
        f.write(await cover_file.read())

    description_path = f"/static/descriptions/{new_id}_description.txt"
    with open(f"static/descriptions/{new_id}_description.txt", "wb") as f:
        f.write(await description_file.read())

    new_movie = {
        "id": new_id,
        "name": name,
        "name_en": name_en,
        "director": director,
        "cost": cost,
        "year": year,
        "is_classic": is_classic,
        "cover_path": cover_path,
        "description_path": description_path
    }
    movies.append(new_movie)

    with open("movies.json", "w", encoding="utf-8") as f:
        json.dump({"movies": movies}, f, ensure_ascii=False, indent=4)

    return {"message": "Фильм добавлен"}

@app.get("/movietop/{movie_name}/detail", response_class=HTMLResponse)
async def movie_detail(request: Request, movie_name: str):
    for movie in movies:
        if movie["name_en"].lower() == movie_name.lower():
            description_content = ""
            if movie.get("description_path") and os.path.exists(movie["description_path"][1:]):
                with open(movie["description_path"][1:], "r", encoding="utf-8") as f:
                    description_content = f.read()
            return templates.TemplateResponse("movie_detail.html", {
                "request": request,
                "movie": movie,
                "description_content": description_content
            })
    raise HTTPException(status_code=404, detail="Фильм не найден")

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == VALID_USER and form_data.password == VALID_PASSWORD:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
        response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=None
        )
        return response
    raise HTTPException(status_code=401, detail="Invalid credentials")

from datetime import datetime
@app.get("/user", response_class=HTMLResponse)
async def user_page(request: Request, current_user: str = Depends(get_current_user)):
    auth_time = datetime.utcnow().isoformat()
    return templates.TemplateResponse("user.html", {
        "request": request,
        "user": current_user,
        "auth_time": auth_time,
        "movies": movies
    })



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8165, reload=True)

