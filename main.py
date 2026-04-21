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
        cursor.execute(f"""
            INSERT INTO Film (Nom,Note,DateSortie,Image,Video,Genre_ID)  
            VALUES('{film.nom}',{film.note},{film.dateSortie},'{film.image}','{film.video}',{film.genreId}) RETURNING *
            """)
        res = cursor.fetchone()
        print(res)
        return res
    
@app.post("/auth/register")
async def register(user : RegisterRequest):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO Utilisateur (Pseudo,AdresseMail,MotDePasse)  
            VALUES('{user.pseudo}','{user.email}','{user.password}') RETURNING *
            """)
        res = cursor.fetchone()
        print(res)
        return res
    
@app.post("/auth/login")
async def login(user: LoginRequest):
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM "Utilisateur" WHERE AdresseMail=? AND MotDePasse=?
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
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Genre")
        res = cursor.fetchall()
        print(res)
        return res

@app.post("/preferences", status_code=201)
async def add_preference(pref: PreferenceRequest, Authorization: str = Header(...)):
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
        
    token = Authorization.split(" ")[1]
    
    try :
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pseudo = payload.get("sub")
        if pseudo is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT rowid FROM Utilisateur WHERE Pseudo = ?", (pseudo,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = user[0]
        
        cursor.execute("SELECT * FROM Genre_utilisateur WHERE ID_Genre=? AND ID_User=?", (pref.genre_id, user_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Preference already exists")
            
        cursor.execute("""
            INSERT INTO Genre_utilisateur (ID_Genre, ID_User)  
            VALUES(?, ?)
            """, (pref.genre_id, user_id))
        conn.commit()
        return {"genre_id": pref.genre_id}
    

@app.delete("/preferences/{genre_id}")
async def remove_preference(genre_id: int, Authorization: str = Header(...)):
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
        
    token = Authorization.split(" ")[1] 
    try :
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pseudo = payload.get("sub")
        if pseudo is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rowid FROM Utilisateur WHERE Pseudo = ?", (pseudo,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = user[0]
        
        cursor.execute("""
            DELETE FROM Genre_utilisateur WHERE ID_Genre = ? AND ID_User = ?
            """, (genre_id, user_id))
            
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Preference not found")
            
        conn.commit()
        return {"genre_id": genre_id}
    
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)