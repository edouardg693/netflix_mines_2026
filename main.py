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
    
@app.post("/preferences")
async def add_preference(Authorization: str, user_id: int, genre_id: int):
    token = Authorization.split(" ")[1]
    try :
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pseudo = payload.get("sub")
        if pseudo is None:
            return {"error": "Invalid token"}
    except jwt.ExpiredSignatureError:
        return {"error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}   

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO Genre_utilisateur (ID_Genre,ID_User)  
            VALUES({genre_id},{user_id}) RETURNING *
            """)
        conn.commit()
        return {"genre_id": genre_id}
    

@app.delete("/preferences/{genre_id}")
async def remove_preference(Authorization: str, user_id: int, genre_id: int):
    token = Authorization.split(" ")[1] 
    try :
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pseudo = payload.get("sub")
        if pseudo is None:
            return {"error": "Invalid token"}
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                DELETE FROM Genre_utilisateur WHERE ID_Genre = {genre_id} AND ID_User = {user_id}
                """)
            conn.commit()
            return {"genre_id": genre_id}
    except jwt.ExpiredSignatureError:
        return {"error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}
    
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)