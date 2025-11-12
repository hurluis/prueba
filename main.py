# python -m uvicorn main:app --reload

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
import os

# Nuevas importaciones para PostgreSQL
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount(
    "/estilos",
    StaticFiles(directory=str(FRONTEND_DIR / "estilos")),
    name="estilos",
)
app.mount(
    "/frontend",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la conexión a la base de datos local
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# --- Modelos Pydantic (sin cambios) ---
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class FeedbackRequest(BaseModel):
    id_property: int
    comment: str
    rating: int
    
class LoginRequest(BaseModel):
    email: str
    password: str

class ReservationRequest(BaseModel):
    property_id: int
    user_id: int
    in_time: str
    out_time: str

# --- Funciones de ayuda para la base de datos ---
def execute_query(query, params=None):
    with engine.connect() as connection:
        try:
            result = connection.execute(text(query), params or {})
            connection.commit() # Importante para INSERT, UPDATE, DELETE
            return result
        except SQLAlchemyError as e:
            print(f"Error en la base de datos: {e}")
            raise HTTPException(status_code=500, detail="Error en la base de datos")

# --- Endpoints ---

@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.post("/register")
async def register(user: RegisterRequest):
    # Verificar si el usuario ya existe
    query_check = 'SELECT * FROM "Users" WHERE email = :email'
    existing_user = execute_query(query_check, {"email": user.email}).first()
    if existing_user:
        return JSONResponse(content={"message": "El usuario ya existe"}, status_code=400)

    # Insertar nuevo usuario
    query_insert = 'INSERT INTO "Users" (name, email, password) VALUES (:name, :email, :password)'
    execute_query(query_insert, user.dict())
    
    return JSONResponse(content={"message": "Usuario registrado con éxito"}, status_code=201)

@app.post("/login")
async def login(user: LoginRequest):
    query = 'SELECT * FROM "Users" WHERE email = :email AND password = :password'
    result = execute_query(query, user.dict()).first()
    
    if not result:
        return JSONResponse(content={"message": "Correo o contraseña incorrectos"}, status_code=400)
    
    user_data = result._asdict()
    return JSONResponse(content={"message": "Inicio de sesión exitoso", "user_id": user_data['id']}, status_code=200)

@app.get("/reserved-dates/{property_id}")
async def get_reserved_dates(property_id: int):
    query = 'SELECT in_time, out_time FROM "Bookings" WHERE property_id = :property_id'
    bookings = execute_query(query, {"property_id": property_id}).fetchall()
    
    reserved_dates = []
    for booking in bookings:
        in_time = booking[0] # Acceso por índice
        out_time = booking[1]
        
        current_date = in_time
        while current_date <= out_time:
            reserved_dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
    
    return JSONResponse(content={"reserved_dates": reserved_dates}, status_code=200)

@app.post("/reserve")
async def reserve(reservation: ReservationRequest):
    try:
        in_time = datetime.strptime(reservation.in_time, "%Y-%m-%d")
        out_time = datetime.strptime(reservation.out_time, "%Y-%m-%d")
    except ValueError:
        return JSONResponse(content={"message": "Formato de fecha inválido. Use YYYY-MM-DD"}, status_code=400)

    if in_time.date() < datetime.now().date():
        return JSONResponse(content={"message": "No puedes reservar fechas pasadas"}, status_code=400)

    # Comprobar si hay reservas que se solapan
    # Una reserva se solapa si (start1 <= end2) and (end1 >= start2)
    query_check = """
        SELECT id FROM "Bookings"
        WHERE property_id = :property_id AND
        in_time <= :out_time AND out_time >= :in_time
    """
    existing_reservation = execute_query(query_check, {"property_id": reservation.property_id, "in_time": in_time, "out_time": out_time}).first()
    if existing_reservation:
        return JSONResponse(content={"message": "La propiedad ya está reservada en esas fechas"}, status_code=400)

    # Crear la nueva reserva
    query_insert = """
        INSERT INTO "Bookings" (property_id, user_id, in_time, out_time, status)
        VALUES (:property_id, :user_id, :in_time, :out_time, 'activo')
    """
    execute_query(query_insert, {
        "property_id": reservation.property_id,
        "user_id": reservation.user_id,
        "in_time": in_time,
        "out_time": out_time
    })

    return JSONResponse(content={"message": "Reserva realizada con éxito"}, status_code=201)

@app.get("/active-reservations/{user_id}")
async def get_active_reservations(user_id: int):
    now = datetime.now()
    # Usamos JOIN para obtener el nombre de la propiedad en una sola consulta
    query = """
        SELECT b.id, b.property_id, p.name AS property_name, b.in_time, b.out_time, b.status
        FROM "Bookings" b
        JOIN "Property" p ON b.property_id = p.id
        WHERE b.user_id = :user_id AND b.out_time >= :now
    """
    reservations = execute_query(query, {"user_id": user_id, "now": now}).fetchall()
    
    active_reservations = [row._asdict() for row in reservations]
    
    return JSONResponse(content={"reservations": active_reservations}, status_code=200)

async def update_expired_reservations():
    now = datetime.now()
    query = 'UPDATE "Bookings" SET status = \'terminado\' WHERE status = \'activo\' AND out_time < :now'
    execute_query(query, {"now": now})
    print("Reservas caducadas actualizadas.")

@app.get("/update-reservations")
async def trigger_update_reservations(background_tasks: BackgroundTasks):
    background_tasks.add_task(update_expired_reservations)
    return {"message": "Actualización de reservas caducadas iniciada"}

@app.get("/past-reservations/{user_id}")
async def get_past_reservations(user_id: int):
    now = datetime.now()
    query = """
        SELECT b.id, b.property_id, p.name AS property_name, b.in_time, b.out_time, b.status
        FROM "Bookings" b
        JOIN "Property" p ON b.property_id = p.id
        WHERE b.user_id = :user_id AND b.out_time < :now
    """
    reservations = execute_query(query, {"user_id": user_id, "now": now}).fetchall()
    
    past_reservations = [row._asdict() for row in reservations]

    return JSONResponse(content={"reservations": past_reservations}, status_code=200)

@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    # La consulta se actualiza para que coincida con la tabla
    query = """
        INSERT INTO "Feedback" (id_property, comment, rating)
        VALUES (:id_property, :comment, :rating)
    """
    execute_query(query, feedback.dict())
    return JSONResponse(content={"message": "Feedback guardado"}, status_code=201)
    
@app.get("/feedback/{property_id}")
async def get_feedback(property_id: int):
    query = 'SELECT * FROM "Feedback" WHERE id_property = :property_id'
    feedback_list = [row._asdict() for row in execute_query(query, {"property_id": property_id}).fetchall()]
    return JSONResponse(content={"feedback": feedback_list}, status_code=200)