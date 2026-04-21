from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from db import get_connection
import jwt
from datetime import datetime, timedelta, timezone
import sqlite3 

SECRET_KEY = "banane"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data:dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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

class RegisterRequest(BaseModel):
    email: str
    pseudo: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class PreferenceRequest(BaseModel):
    genre_id: int

@app.post("/film")
async def createFilm(film : Film):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Film (Nom, Note, DateSortie, Image, Video, Genre_ID)  
            VALUES(?, ?, ?, ?, ?, ?) RETURNING *
            """, (film.nom, film.note, film.dateSortie, film.image, film.video, film.genreId))
        res = cursor.fetchone()
        return res
    
@app.post("/auth/register")
async def register(user : RegisterRequest):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Utilisateur (Pseudo, AdresseMail, MotDePasse)  
            VALUES(?, ?, ?) RETURNING *
            """, (user.pseudo, user.email, user.password))
        res = cursor.fetchone()
        return res
    
@app.post("/auth/login")
async def login(user: LoginRequest):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM Utilisateur WHERE AdresseMail=? AND MotDePasse=?
            """, (user.email, user.password))
        res = cursor.fetchone()
        
        if res is None:
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        pseudo_utilisateur = res[1] 
        jwt_token = create_access_token({"sub": pseudo_utilisateur})
        
        return {"access_token": jwt_token, "token_type": "bearer"}

@app.get("/films")
async def get_film_page(page: int = 1, per_page: int = 20, genre_id: int | None = None):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        where_clause = ""
        params = []
        
        if genre_id is not None:
            where_clause = "WHERE Genre_ID = ?"
            params.append(genre_id)
            
        cursor.execute(f"SELECT COUNT(*) FROM Film {where_clause}", params)
        total = cursor.fetchone()[0]

        query = f"""
            SELECT rowid as ID, * FROM Film 
            {where_clause} 
            ORDER BY DateSortie DESC 
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [per_page, offset])
        films = [dict(row) for row in cursor.fetchall()]
        
        return {
            "data": films,
            "page": page,
            "per_page": per_page,
            "total": total
        }

@app.get("/films/{film_id}")
def getFilm(film_id: int):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        cursor.execute("SELECT rowid as ID, * FROM Film WHERE rowid = ? OR Id = ?", (film_id, film_id))
        res = cursor.fetchone()
        
        if res is None:
            raise HTTPException(status_code=404, detail="Film introuvable")
            
        return dict(res)

@app.get("/genres")
def getGenres():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row # Ajouté pour renvoyer des dictionnaires propres
        cursor = conn.cursor()
        cursor.execute("SELECT rowid as ID, * FROM Genre")
        res = [dict(row) for row in cursor.fetchall()]
        return res
    
@app.post("/preferences")
async def add_preference(pref: PreferenceRequest, Authorization: str = Header(None)):
    if Authorization is None or not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou mal formaté")
        
    token = Authorization.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pseudo = payload.get("sub")
        if pseudo is None:
            raise HTTPException(status_code=401, detail="Token invalide")
    except Exception:
        raise HTTPException(status_code=401, detail="Token expiré ou invalide")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rowid FROM Utilisateur WHERE Pseudo = ?", (pseudo,))
        user_row = cursor.fetchone()
        
        if not user_row:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
            
        user_id = user_row[0]

        cursor.execute("""
            INSERT INTO Genre_utilisateur (ID_Genre, ID_User)  
            VALUES(?, ?)
            """, (pref.genre_id, user_id))
        conn.commit()
        
        return {"genre_id": pref.genre_id}
    

@app.delete("/preferences/{genre_id}")
async def remove_preference(genre_id: int, Authorization: str = Header(None)):
    if Authorization is None or not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou mal formaté")
        
    token = Authorization.split(" ")[1] 
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pseudo = payload.get("sub")
        if pseudo is None:
             raise HTTPException(status_code=401, detail="Token invalide")
    except Exception:
         raise HTTPException(status_code=401, detail="Token expiré ou invalide")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rowid FROM Utilisateur WHERE Pseudo = ?", (pseudo,))
        user_row = cursor.fetchone()
        
        if not user_row:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
            
        user_id = user_row[0]

        cursor.execute("""
            DELETE FROM Genre_utilisateur WHERE ID_Genre = ? AND ID_User = ?
            """, (genre_id, user_id))
        conn.commit()
        return {"genre_id": genre_id}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)