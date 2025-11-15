import json
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from models import Movietop

app = FastAPI()


app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


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

sessions = {}


VALID_USER = "admin"
VALID_PASSWORD = "admin"


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
async def add_movie_form(request: Request):
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
        cover_file: UploadFile = File(...)
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

    # Обновляем movies.json
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
async def login(response: Response, username: str = Form(...), password: str = Form(...)):

    if username == VALID_USER and password == VALID_PASSWORD:
        token = str(uuid.uuid4())
        sessions[token] = {"user": username, "auth_time": datetime.now()}
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            max_age=120,
            secure=True,
            samesite="lax"
        )
        return {"message": "Login successful"}

    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/user")
async def user(request: Request):

    token = request.cookies.get("session_token")

    # Проверяем наличие токена
    if not token:
        return JSONResponse(
            content={"message": "Unauthorized"},
            status_code=401
        )


    if token not in sessions:
        return JSONResponse(
            content={"message": "Unauthorized"},
            status_code=401
        )

    session = sessions[token]
    now = datetime.now()

    if now - session["auth_time"] > timedelta(minutes=2):

        del sessions[token]
        return JSONResponse(
            content={"message": "Unauthorized"},
            status_code=401
        )

    session["auth_time"] = now
    profile = {"user": session["user"]}
    auth_time = session["auth_time"].isoformat()

    return {
        "profile": profile,
        "auth_time": auth_time,
        "movies": movies
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)


