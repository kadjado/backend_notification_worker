
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router
from app.routes.structures import router as structures_router
from app.routes.fiches import router as fiches_router
from app.routes.notifications import router as notifications_router
from app.routes.whatsapp_webhook import router as whatsapp_webhook_router

app = FastAPI(
    title="SCDIP - PNLP",
    description="API de collecte des donnÃ©es individuelles du paludisme",
    version="0.1.0",
)

# Configuration CORS pour le frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://scdip-pnlp.vercel.app",
        "http://192.168.29.142:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routes
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(structures_router)
app.include_router(fiches_router)
app.include_router(notifications_router)
app.include_router(whatsapp_webhook_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "application": "SCDIP-PNLP"}

