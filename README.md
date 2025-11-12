# 🏡 Plataforma de Reservas de Propiedades

Aplicación tipo Airbnb compuesta por un backend *FastAPI* y un conjunto de páginas HTML/CSS estáticas. El backend expone una API REST para gestionar usuarios, propiedades, reservas y feedback, persiste en SQLite o PostgreSQL y sirve los assets del frontend cuando se ejecuta localmente o dentro del contenedor.

## 🧱 Arquitectura

| Capa | Descripción |
| --- | --- |
| Backend | Servicio FastAPI (backend/main.py) con ORM ligero basado en SQLAlchemy, inicialización de tablas y sembrado automático de propiedades para sincronizarse con el frontend. |
| Frontend | Vistas estáticas (frontend/*.html) que consumen la API mediante fetch, se estilizan con TailwindCSS y se sirven con FastAPI o un contenedor Nginx. |
| Base de datos | SQLite por defecto (backend/app.db) o PostgreSQL si se define DATABASE_URL. |

## 📁 Estructura del repositorio


├── backend/
│   ├── Dockerfile                 # Imagen del backend (python:3.11-slim + deps)
│   ├── main.py                    # FastAPI (API + seed + estáticos /estilos)
│   ├── requirements.txt           # Incluye uvicorn, fastapi, sqlalchemy, pydantic, psycopg2-binary, authlib, python-dotenv
│   ├── tests/
│   │   └── test_main.py           # Tests de API (sqlite file en CI)
│   └── static/                    # Recursos extra si los usas
│
├── frontend/
│   ├── *.html                     # Vistas públicas
│   ├── estilos/
│   │   ├── api.js                 # BASE_URL de la API (ej: http://localhost:8000)
│   │   └── styles.css             # Estilos
│   ├── nginx.conf                 # Nginx CORREGIDO (sirve /estilos local, proxy /api y /auth sin duplicar)
│   └── Dockerfile                 # Imagen Nginx (copia html + nginx.conf)
│
├── .github/
│   └── workflows/
│       └── build.yml              # CI/CD: pytest + build/push (push solo en main, con workflow_dispatch)
│
├── docker-compose.yml             # Orquestación backend, frontend y Postgres
├── .env.example                   # GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (ejemplo)
├── .dockerignore                  # Ignora venv, __pycache__, etc. (raíz y/o backend/frontend)
├── LICENSE.txt
├── README.md
└── (opcional) eliminar:
    ├── Dockerfile.backend         # ← legado, ya no se usa
    ├── main.py                    # ← raíz (histórico), usar backend/main.py
    └── requirements.txt           # ← raíz (histórico), usar backend/requirements.txt



> ℹ El backend de referencia se encuentra en backend/main.py. El main.py de la raíz se conserva únicamente por compatibilidad con despliegues antiguos.

## 🧩 Funcionalidades del backend

- Autenticación simple: registro y login con almacenamiento de credenciales.
- Gestión de propiedades: catálogo precargado con cinco inmuebles y consultas desde el frontend.
- Reservas con validaciones: bloqueo de solapamientos, verificación de fechas futuras y actualización de estados vencidos mediante tareas en segundo plano.
- Historial del usuario: endpoints para reservas activas y pasadas.
- Feedback: envío y consulta de comentarios por propiedad.

## 🌐 Endpoints principales

Las rutas están disponibles tanto en / como con el prefijo /api.

| Método | Ruta | Descripción |
| ------ | ---- | ----------- |
| POST | /register | Crea un usuario y devuelve su id. |
| POST | /login | Valida credenciales y responde con el user_id. |
| GET | /reserved-dates/{property_id} | Lista fechas ocupadas para el calendario de reservas. |
| POST | /reserve | Crea una reserva si no hay solapamientos y la fecha es futura. |
| GET | /active-reservations/{user_id} | Obtiene reservas activas con detalles de la propiedad. |
| GET | /update-reservations | Actualiza en segundo plano las reservas expiradas. |
| GET | /past-reservations/{user_id} | Devuelve reservas históricas del usuario. |
| POST | /cancel-reservation | Cancela una reserva activa antes del check-in. |
| POST | /feedback | Almacena un comentario y calificación para una propiedad. |
| GET | /feedback/{property_id} | Recupera todos los comentarios asociados a la propiedad. |

## 🖥 Ejecución local

1. *Crear y activar entorno virtual (opcional):*
   bash
   python -m venv .venv
   source .venv/bin/activate
   
2. *Instalar dependencias del backend:*
   bash
   pip install -r backend/requirements.txt
   
3. *Configurar variables de entorno (si aplica):*
   - DATABASE_URL: cadena SQLAlchemy. Si no se define, se crea backend/app.db con SQLite.
   - FRONTEND_DIR: ruta alternativa al directorio frontend/.
   - GOOGLE_CLIENT_ID: ID del cliente OAuth de Google (requerido para login con Google).
   - GOOGLE_CLIENT_SECRET: Secreto del cliente OAuth de Google (requerido para login con Google).
   - SESSION_SECRET_KEY: Clave secreta para sesiones (opcional, se genera automáticamente si no se define).
   - Opcionalmente coloca estas claves en un archivo .env; load_dotenv() las leerá automáticamente.

   ### Configuración de credenciales de Google OAuth

   Para habilitar el login con Google, necesitas crear un proyecto en Google Cloud Console:

   1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
   2. Crea un nuevo proyecto o selecciona uno existente.
   3. Habilita la API de Google+ (si no está habilitada).
   4. Ve a "Credenciales" en el menú lateral.
   5. Haz clic en "Crear credenciales" > "ID de cliente de OAuth".
   6. Selecciona "Aplicación web" como tipo de aplicación.
   7. En "Orígenes de JavaScript autorizados", agrega: http://localhost
   8. En "URI de redireccionamiento autorizados", agrega: http://localhost/auth/google/callback
   9. Copia el "ID de cliente" y el "Secreto de cliente".
   10. Crea un archivo .env en la raíz del proyecto con:
       
       GOOGLE_CLIENT_ID=tu_id_de_cliente_aqui
       GOOGLE_CLIENT_SECRET=tu_secreto_de_cliente_aqui
       
   11. Para desarrollo local, cambia el tipo de aplicación a "Aplicación de escritorio" en lugar de "Aplicación web" para permitir localhost como URI de redireccionamiento.

4. *Inicializar y levantar FastAPI:*
   bash
   uvicorn backend.main:app --reload
   
5. *Abrir el frontend:*
   - http://localhost:8000/ muestra la landing (index.html).
   - El backend sirve /frontend, /estilos y los archivos estáticos registrados.

Durante el primer arranque se crean las tablas necesarias y se insertan los registros iniciales de propiedades para mantener sincronizado el catálogo.


## ⚙ Integración Continua (CI/CD) con GitHub Actions

Este proyecto está configurado con *GitHub Actions* para automatizar la construcción y despliegue de las imágenes Docker del backend y frontend.

Cada vez que se hace **push o merge a la rama main**:

✅ Se ejecutan las pruebas del backend (si existen)  
✅ Se construyen las imágenes Docker del backend y frontend  
✅ Se publican automáticamente en *Docker Hub*, listas para usar con docker-compose


---

## 🧱 Flujo Automatizado

📌 *Archivo del workflow:*  
.github/workflows/docker-build.yml

🔑 *Acciones principales:*

| Acción | Descripción |
|--------|-------------|
| docker/login-action | Autentica en Docker Hub |
| docker/build-push-action | Construye y publica las imágenes Docker |

🧩 *Resultado:*  
Las imágenes se suben a Docker Hub con las etiquetas:

- :latest
- :1.0

---

## 🐋 Imágenes públicas disponibles en Docker Hub

Puedes descargar y usar las imágenes directamente, sin necesidad de clonar el repositorio:

| Servicio | Imagen | Comando |
|----------|--------|---------|
| *Backend* | julilyherrera/airbnb-backend:latest | docker pull julilyherrera/airbnb-backend:latest |
| *Frontend* | `julilyherrera/airbnb-frontend:latest ` | docker pull julilyherrera/airbnb-frontend:latest |

---

### 🔄 Actualización automática

Estas imágenes se regeneran y publican automáticamente cada vez que se actualiza la rama main, gracias al pipeline configurado con GitHub Actions.

🚀 Esto asegura que las versiones en Docker Hub siempre estén sincronizadas con los últimos cambios del proyecto.



## 🐳 Despliegue con Docker Compose

- Imágenes públicas: https://hub.docker.com/repositories/eritzsm

### Pasos rápidos para clonar y levantar los contenedores

1. Asegúrate de tener *Docker Desktop* abierto y en ejecución.
2. Clona el repositorio:
   bash
   git clone https://github.com/JULILYHERRERA/AIRBNB_GESTION.git
   
3. Entra a la carpeta del proyecto:
   bash
   cd AIRBNB_GESTION/
   
4. (Opcional) Define DATABASE_URL y otras credenciales en .env para que Compose las consuma.
5. Levanta los servicios:
   bash
   docker compose up --build
   
6. Accede a:
   - http://localhost:8000 para el frontend servido por Nginx.
   - http://localhost:8000/docs para la documentación interactiva (swagger ui).

Servicios incluidos en docker-compose.yml:
- *fastapi-backend*: ejecuta backend/main.py, monta el directorio frontend/ como recursos estáticos y expone la API REST.
- *nginx-frontend*: entrega las páginas HTML precompiladas con la configuración de frontend/nginx.conf.
- *local-postgres-db*: instancia PostgreSQL 15 con volumen persistente booking-postgres-data.

---

## ☸️ Despliegue en Minikube (Kubernetes)

Para ejecutar la aplicación en un cluster Kubernetes local usando Minikube:

### Requisitos previos

- **Minikube** instalado y corriendo: `minikube start --driver=docker`
- **kubectl** configurado para acceder a Minikube
- **Docker** disponible (para compilar imágenes locales)
- Credenciales de Google OAuth si quieres probar login con Google

### Pasos para desplegar

1. **Clona el repositorio:**
   bash
   git clone https://github.com/JULILYHERRERA/AIRBNB_GESTION.git
   cd AIRBNB_GESTION/
   

2. **Compila las imágenes Docker localmente** (en el contexto de Docker de Minikube):
   bash
   docker build -f Dockerfile.backend -t airbnb-backend:local . --no-cache
   docker build -f frontend/Dockerfile -t airbnb-frontend:local ./frontend --no-cache
   

3. **Crea los Secrets y ConfigMaps** con tus credenciales:
   
   Edita `secret.yaml` con tus valores:
   bash
   apiVersion: v1
   kind: Secret
   metadata:
     name: airbnb-secret
   type: Opaque
   stringData:
     POSTGRES_PASSWORD: "tu-contraseña-postgres"
     GOOGLE_CLIENT_ID: "tu-google-client-id"
     GOOGLE_CLIENT_SECRET: "tu-google-client-secret"
   
   
   Aplica el Secret:
   bash
   kubectl apply -f secret.yaml
   kubectl apply -f configmap.yaml
   kubectl apply -f service.yaml
   

4. **Despliega los servicios en Minikube:**
   bash
   kubectl apply -f deployment.yaml
   

5. **Verifica que todos los pods estén Running:**
   bash
   kubectl get pods
   # Deberías ver: backend, frontend y postgres en estado Running
   

6. **Establece los port-forwards** (necesario en Minikube con Docker driver en Windows):
   
   En una terminal abierta:
   bash
   kubectl port-forward svc/frontend-service 8080:80 --address=127.0.0.1
   
   
   En otra terminal abierta:
   bash
   kubectl port-forward svc/backend-service 8000:8000 --address=127.0.0.1
   

7. **Accede a la aplicación:**
   - Frontend: http://localhost:8080
   - Backend API: http://localhost:8000
   - Swagger API Docs: http://localhost:8000/docs

### Configuración importante para Google OAuth en Minikube

Si quieres que funcione el login con Google en tu instalación local de Minikube:

1. En **Google Cloud Console**, registra estas URIs de redirección:
   - `http://localhost:8000/auth/google/callback`
   - `http://localhost:8080/auth/google/callback`

2. Asegúrate de que `secret.yaml` contenga:
   bash
   GOOGLE_CLIENT_ID: tu-id
   GOOGLE_CLIENT_SECRET: tu-secreto
   

3. Aplica los cambios:
   bash
   kubectl apply -f secret.yaml
   kubectl rollout restart deployment/backend
   

### Troubleshooting en Minikube

**Problema:** Pod en `CrashLoopBackOff`
- Revisa logs: `kubectl logs deployment/backend`
- Verifica env vars: `kubectl describe pod <pod-name>`

**Problema:** "localhost rechazó la conexión" en Google login
- Asegúrate de que ambos port-forwards estén activos
- Verifica que la redirect URI en Google Cloud Console sea exacta

**Problema:** Backend no conecta a PostgreSQL
- Verifica: `kubectl logs deployment/backend --tail=50 | grep -i postgre`
- Confirma que el Secret tiene la contraseña correcta

**Limpiar todo y reintentar:**
bash
kubectl delete -f deployment.yaml -f service.yaml -f configmap.yaml -f secret.yaml
docker rmi airbnb-backend:local airbnb-frontend:local
# Repetir los pasos desde el paso 2