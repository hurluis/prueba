# python -m uvicorn main:app --reload

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import os
from authlib.integrations.starlette_client import OAuth
import httpx


# Nuevas importaciones para PostgreSQL
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from prometheus_fastapi_instrumentator import Instrumentator

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

frontend_dir_env = os.getenv("FRONTEND_DIR")
if frontend_dir_env:
    FRONTEND_DIR = Path(frontend_dir_env).resolve()
else:
    candidate = (BASE_DIR / "frontend").resolve()
    if not candidate.exists():
        candidate = (BASE_DIR.parent / "frontend").resolve()
    FRONTEND_DIR = candidate

if not FRONTEND_DIR.exists():
    raise RuntimeError(f"Frontend directory '{FRONTEND_DIR}' does not exist")

# Base URL used to redirect users to the frontend after OAuth/login flows.
# Make this configurable so local testing (with port-forward) and deployed
# environments can use the appropriate host/port.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:8080")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "super-secret-key"))

# Instrumentación de Prometheus
Instrumentator().instrument(app).expose(app)

# Mount static files - try /app/static first, then fallback to frontend/estilos
static_dir = BASE_DIR / "static"
if not static_dir.exists():
    static_dir = FRONTEND_DIR / "estilos"
if static_dir.exists():
    app.mount('/static', StaticFiles(directory=static_dir), name="static")
    app.mount('/estilos', StaticFiles(directory=static_dir), name="estilos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar OAuth (Google)
oauth = OAuth()

# Crear cliente HTTP asíncrono para OAuth (necesario para Authlib con FastAPI)
httpx_client = httpx.AsyncClient(timeout=30.0)

# Verificar que las variables de entorno estén configuradas
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("⚠️  ADVERTENCIA: GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET no están configurados")
    print("⚠️  La autenticación con Google no funcionará sin estas variables")
else:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "timeout": 30.0
        }
    )

# Configuración de la conexión a la base de datos local
DATABASE_URL = os.getenv("DATABASE_URL")
IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"

if not IS_DOCKER:
    # When running locally, use SQLite
    DATABASE_URL = f"sqlite:///{BASE_DIR / 'app.db'}"
elif not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set when running in Docker")

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
IS_SQLITE = engine.url.get_backend_name() == "sqlite"

if IS_SQLITE:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db():
    """Crea las tablas necesarias si no existen."""
    if IS_SQLITE:
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS "Users" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "Property" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                location TEXT,
                price NUMERIC(10, 2),
                description TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "Bookings" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                in_time DATE NOT NULL,
                out_time DATE NOT NULL,
                status VARCHAR(50) DEFAULT 'activo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(property_id) REFERENCES "Property"(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES "Users"(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "Feedback" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_property INTEGER NOT NULL,
                comment TEXT NOT NULL,
                rating INTEGER CHECK (rating BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(id_property) REFERENCES "Property"(id) ON DELETE CASCADE
            )
            """
        ]
    else:
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS "Users" (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "Property" (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                location TEXT,
                price NUMERIC(10, 2),
                description TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "Bookings" (
                id SERIAL PRIMARY KEY,
                property_id INTEGER NOT NULL REFERENCES "Property"(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
                in_time DATE NOT NULL,
                out_time DATE NOT NULL,
                status VARCHAR(50) DEFAULT 'activo',
                created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "Feedback" (
                id SERIAL PRIMARY KEY,
                id_property INTEGER NOT NULL REFERENCES "Property"(id) ON DELETE CASCADE,
                comment TEXT NOT NULL,
                rating INTEGER CHECK (rating BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        ]

    with engine.begin() as connection:
        for ddl in ddl_statements:
            connection.execute(text(ddl))


# Datos iniciales de propiedades para garantizar la coherencia con el frontend
INITIAL_PROPERTIES = [
    {
        "id": 1,
        "name": "Apartamento en El Poblado",
        "location": "Cl. 9 #37, El Poblado, Medellín, Antioquia",
        "price": 450000,
        "description": "Hermoso apartamento en una de las mejores zonas de Medellín, cerca de centros comerciales y restaurantes.",
        "image_url": "https://images.ctfassets.net/8lc7xdlkm4kt/33L5l2aTXdJAAEfw55n0Yh/7472faf6b498fdc11091fc65a5c69165/render-sobre-planos-saint-michel.jpg",
    },
    {
        "id": 2,
        "name": "Casa colonial en Cartagena",
        "location": "10-46 Media Luna 10, Getsemaní, Cartagena de Indias, Bolívar",
        "price": 500000,
        "description": "Encantadora casa colonial con vistas al mar, en el centro histórico de Cartagena.",
        "image_url": "https://media-luna-hostel.cartagena-hotels.net/data/Photos/1080x700w/10392/1039228/1039228984/cartagena-media-luna-hostel-photo-1.JPEG",
    },
    {
        "id": 3,
        "name": "Loft en Bogotá",
        "location": "Av Suba #125-98, Bogotá",
        "price": 320000,
        "description": "Moderno loft en el centro de Bogotá, ideal para viajeros de negocios.",
        "image_url": "https://latinexclusive.com/sites/default/files/styles/main_property_slide/public/api_file_downloads/3862061_1.jpg?itok=qxmdZ3oA",
    },
    {
        "id": 4,
        "name": "Cabaña en el Eje Cafetero",
        "location": "2 kilómetros antes de termales Santa Rosa por la desviación a la Paloma vereda, San RAMON, Santa Rosa de Cabal, Risaralda",
        "price": 800000,
        "description": "Cabaña rústica rodeada de naturaleza, perfecta para desconectarse y disfrutar del café colombiano.",
        "image_url": "https://asoaturquindio.com/wp-content/uploads/2023/09/cabanas-la-herradura-4-1.jpg",
    },
    {
        "id": 5,
        "name": "Hostal en Santa Marta",
        "location": "Cl. 14 #3-58, Comuna 2, Santa Marta, Magdalena",
        "price": 50000,
        "description": "Hostal económico a pocos minutos de la playa, ideal para mochileros y aventureros.",
        "image_url": "https://cf.bstatic.com/xdata/images/hotel/max500/151251581.jpg?k=02b942afead8be7bea67cd35453662d8a6ae787336565b884c55aca6dbedcd08&o=",
    },
]


def seed_initial_properties():
    """Inserta propiedades base si la tabla está vacía o faltan entradas esperadas."""

    with engine.begin() as connection:
        for property_data in INITIAL_PROPERTIES:
            exists = connection.execute(
                text('SELECT 1 FROM "Property" WHERE id = :id'),
                {"id": property_data["id"]},
            ).scalar()

            if exists:
                continue

            connection.execute(
                text(
                    'INSERT INTO "Property" (id, name, location, price, description, image_url) '
                    'VALUES (:id, :name, :location, :price, :description, :image_url)'
                ),
                property_data,
            )

        if not IS_SQLITE:
            connection.execute(
                text(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('"Property"', 'id'),
                        (SELECT COALESCE(MAX(id), 0) FROM "Property")
                    )
                    """
                )
            )


init_db()
seed_initial_properties()

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


class CancelReservationRequest(BaseModel):
    booking_id: int
    user_id: int

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

api_router = APIRouter()


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{page_name}.html")
def serve_html_page(page_name: str):
    """Devuelve archivos HTML estáticos del frontend.

    Permite navegar directamente a rutas como ``/detalle.html`` sin
    depender de un servidor externo y evita interferir con las rutas de la API,
    ya que solo intercepta solicitudes que terminan en ``.html``.
    """

    target_file = (FRONTEND_DIR / f"{page_name}.html").resolve()

    try:
        target_file.relative_to(FRONTEND_DIR)
    except ValueError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

    if not target_file.exists():
        raise HTTPException(status_code=404, detail="Página no encontrada")

    return FileResponse(target_file)


@api_router.post("/register")
async def register(user: RegisterRequest):
    # Verificar si el usuario ya existe
    query_check = 'SELECT * FROM "Users" WHERE email = :email'
    existing_user = execute_query(query_check, {"email": user.email}).first()
    if existing_user:
        return JSONResponse(content={"message": "El usuario ya existe"}, status_code=400)

    # Insertar nuevo usuario
    if IS_SQLITE:
        query_insert = 'INSERT INTO "Users" (name, email, password) VALUES (:name, :email, :password)'
        result = execute_query(query_insert, user.dict())
        user_id = result.lastrowid
    else:
        query_insert = 'INSERT INTO "Users" (name, email, password) VALUES (:name, :email, :password) RETURNING id'
        result = execute_query(query_insert, user.dict())
        user_id = result.scalar()

    return JSONResponse(content={"message": "Usuario registrado con éxito", "user_id": user_id}, status_code=201)


@api_router.post("/login")
async def login(user: LoginRequest):
    query = 'SELECT * FROM "Users" WHERE email = :email AND password = :password'
    result = execute_query(query, user.dict()).first()
    
    if not result:
        return JSONResponse(content={"message": "Correo o contraseña incorrectos"}, status_code=400)
    
    user_data = result._asdict()
    return JSONResponse(content={"message": "Inicio de sesión exitoso", "user_id": user_data['id']}, status_code=200)


# --- Google OAuth endpoints ---
auth_router = APIRouter()

@auth_router.get("/auth/google/login")
async def google_login(request: Request):
    """Inicia el flujo de OAuth2 con Google redirigiendo al consentimiento."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth no está configurado en el servidor")
    
    # Para desarrollo local, permitir sobreescribir la redirect URI desde una variable de entorno.
    # Por defecto usamos localhost:8000 para que el port-forward a ese puerto funcione en pruebas locales.
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        # Ya se verifica más arriba, pero dejamos un log claro aquí.
        print("⚠️  ADVERTENCIA: GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET no están configurados")
        print(f"🔐 Usando redirect_uri (pero auth no configurado): {redirect_uri}")
    else:
        print(f"🔐 Iniciando login con Google - Redirect URI: {redirect_uri}")

    return await oauth.google.authorize_redirect(request, redirect_uri)


@auth_router.get("/auth/google/callback")
async def google_auth_callback(request: Request):
    """Callback que Google llamará tras la autenticación."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth no está configurado en el servidor")
    
    try:
        print("🔄 Procesando callback de Google...")
        token = await oauth.google.authorize_access_token(request)
        print("✅ Token de acceso recibido")
    except Exception as e:
        print(f"❌ Error en autorización de Google: {e}")
        raise HTTPException(status_code=400, detail=f"Error en autorización de Google: {e}")

    # Obtener datos del usuario desde el endpoint userinfo
    try:
        resp = await oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        user_info = resp.json()
        print(f"📧 Información del usuario: {user_info}")
    except Exception as e:
        print(f"❌ Error obteniendo información del usuario: {e}")
        raise HTTPException(status_code=400, detail="No se pudo obtener la información del usuario de Google")

    email = user_info.get("email")
    name = user_info.get("name") or user_info.get("given_name") or "Usuario Google"

    if not email:
        print("❌ No se pudo obtener el email del usuario")
        raise HTTPException(status_code=400, detail="No se pudo obtener el correo de la cuenta de Google")

    # Buscar o crear el usuario en la base de datos
    query_check = 'SELECT * FROM "Users" WHERE email = :email'
    existing_user = execute_query(query_check, {"email": email}).first()

    if existing_user:
        user_id = existing_user._mapping["id"]
        print(f"✅ Usuario existente encontrado: ID {user_id}")
    else:
        # Insertar usuario con contraseña vacía para autenticación Google
        print(f"👤 Creando nuevo usuario: {name} ({email})")
        if IS_SQLITE:
            query_insert = 'INSERT INTO "Users" (name, email, password) VALUES (:name, :email, :password)'
            result = execute_query(query_insert, {"name": name, "email": email, "password": ""})
            user_id = result.lastrowid
        else:
            query_insert = 'INSERT INTO "Users" (name, email, password) VALUES (:name, :email, :password) RETURNING id'
            result = execute_query(query_insert, {"name": name, "email": email, "password": ""})
            user_id = result.scalar()
        print(f"✅ Nuevo usuario creado: ID {user_id}")

    # Redirigir al frontend con el user_id en la URL. Usar la base URL absoluta
    # para que el navegador sea dirigido al servidor frontend (ej. localhost:8080)
    frontend_url = f"{FRONTEND_BASE_URL}/index.html?google_login_success=true&user_id={user_id}"
    print(f"🔄 Redirigiendo al frontend: {frontend_url}")
    return RedirectResponse(url=frontend_url)


@auth_router.get("/auth/google/success")
async def google_login_success(user_id: int):
    """Endpoint para verificar el éxito del login con Google."""
    return JSONResponse(content={
        "message": "Inicio de sesión con Google exitoso", 
        "user_id": user_id
    }, status_code=200)

def ensure_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return datetime.fromisoformat(value).date()
    raise ValueError("Formato de fecha desconocido")


def row_to_serializable_dict(row):
    data = dict(row._mapping)

    for key, value in data.items():
        if isinstance(value, (datetime, date)):
            data[key] = value.isoformat()

    return data


def serialize_reservation_row(row):
    return row_to_serializable_dict(row)


@api_router.get("/reserved-dates/{property_id}")
async def get_reserved_dates(property_id: int):
    query = (
        'SELECT in_time, out_time FROM "Bookings" '
        "WHERE property_id = :property_id AND status = 'activo'"
    )
    bookings = execute_query(query, {"property_id": property_id}).fetchall()

    reserved_dates = []
    for booking in bookings:
        in_time = ensure_date(booking[0])
        out_time = ensure_date(booking[1])

        current_date = in_time
        while current_date <= out_time:
            reserved_dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
    
    return JSONResponse(content={"reserved_dates": reserved_dates}, status_code=200)

@api_router.post("/reserve")
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
        status = 'activo' AND
        in_time <= :out_time AND out_time >= :in_time
    """
    existing_reservation = execute_query(
        query_check,
        {"property_id": reservation.property_id, "in_time": in_time, "out_time": out_time},
    ).first()
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

@api_router.get("/active-reservations/{user_id}")
async def get_active_reservations(user_id: int):
    now = datetime.now()
    # Usamos JOIN para obtener el nombre de la propiedad en una sola consulta
    query = """
        SELECT b.id, b.property_id, p.name AS property_name, b.in_time, b.out_time, b.status
        FROM "Bookings" b
        JOIN "Property" p ON b.property_id = p.id
        WHERE b.user_id = :user_id AND b.out_time >= :now AND b.status = 'activo'
    """
    reservations = execute_query(query, {"user_id": user_id, "now": now}).fetchall()
    
    active_reservations = [
        serialize_reservation_row(row)
        for row in reservations
    ]

    return JSONResponse(content={"reservations": active_reservations}, status_code=200)

async def update_expired_reservations():
    now = datetime.now()
    query = 'UPDATE "Bookings" SET status = \'terminado\' WHERE status = \'activo\' AND out_time < :now'
    execute_query(query, {"now": now})
    print("Reservas caducadas actualizadas.")

@api_router.get("/update-reservations")
async def trigger_update_reservations(background_tasks: BackgroundTasks):
    background_tasks.add_task(update_expired_reservations)
    return {"message": "Actualización de reservas caducadas iniciada"}

@api_router.get("/past-reservations/{user_id}")
async def get_past_reservations(user_id: int):
    now = datetime.now()
    query = """
        SELECT b.id, b.property_id, p.name AS property_name, b.in_time, b.out_time, b.status
        FROM "Bookings" b
        JOIN "Property" p ON b.property_id = p.id
        WHERE b.user_id = :user_id AND b.out_time < :now
    """
    reservations = execute_query(query, {"user_id": user_id, "now": now}).fetchall()

    past_reservations = [
        serialize_reservation_row(row)
        for row in reservations
    ]

    return JSONResponse(content={"reservations": past_reservations}, status_code=200)


@api_router.post("/cancel-reservation")
async def cancel_reservation(payload: CancelReservationRequest):
    booking = execute_query(
        'SELECT id, in_time, status FROM "Bookings" WHERE id = :booking_id AND user_id = :user_id',
        {"booking_id": payload.booking_id, "user_id": payload.user_id},
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    booking_data = booking._mapping
    if booking_data["status"] != "activo":
        return JSONResponse(content={"message": "La reserva ya no está activa"}, status_code=400)

    check_in_date = ensure_date(booking_data["in_time"])
    today = datetime.now().date()

    if check_in_date <= today:
        return JSONResponse(content={"message": "Solo puedes cancelar antes del día de ingreso"}, status_code=400)

    execute_query(
        "UPDATE \"Bookings\" SET status = 'cancelado' WHERE id = :booking_id",
        {"booking_id": payload.booking_id},
    )

    return JSONResponse(content={"message": "Reserva cancelada con éxito"}, status_code=200)

@api_router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    # La consulta se actualiza para que coincida con la tabla
    query = """
        INSERT INTO "Feedback" (id_property, comment, rating)
        VALUES (:id_property, :comment, :rating)
    """
    execute_query(query, feedback.dict())
    return JSONResponse(content={"message": "Feedback guardado"}, status_code=201)
    
@api_router.get("/feedback/{property_id}")
async def get_feedback(property_id: int):
    query = 'SELECT * FROM "Feedback" WHERE id_property = :property_id'
    feedback_list = [
        row_to_serializable_dict(row)
        for row in execute_query(query, {"property_id": property_id}).fetchall()
    ]
    return JSONResponse(content={"feedback": feedback_list}, status_code=200)


app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="")
