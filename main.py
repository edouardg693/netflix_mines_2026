from fastapi import FastAPI
from pydantic import BaseModel
from db import get_connection

app = FastAPI()


@app.get("/ping")
def ping():
    return {"message": "pong"}

class Film(BaseModel):
    id: int | None = None
    nom: str
    note: float | None = None
    dateSortie: int
    image: str | None = None
    video: str | None = None
    genreId: int | None = None

@app.post("/film")
async def createFilm(film : Film):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO Film (Nom,Note,DateSortie,Image,Video)  
            VALUES('{film.nom}',{film.note},{film.dateSortie},'{film.image}','{film.video}') RETURNING *
            """)
        res = cursor.fetchone()
        print(res)
        return res

@app.get("/films/{film_id}")
def getFilm(film_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Film WHERE Id = ?", (film_id,))
        res = cursor.fetchone()
        return res

@app.get("/genres")
def getGenres():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Genre")
        res = cursor.fetchall()
        return res
    


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
