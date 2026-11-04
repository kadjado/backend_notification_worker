
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router
from app.routes.structures import router as structures_router
from app.routes.fiches import router as fiches_router
from app.routes.notifications import router as notifications_router
from app.routes.whatsapp_webhook import router as whatsapp_webhook_router
from app.routes.rapports import router as rapports_router
from app.workers.notifications import run_worker


logger = logging.getLogger("scdip.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarre et arrête automatiquement le worker avec FastAPI."""

    stop_event = threading.Event()

    worker_thread = threading.Thread(
        target=run_worker,
        args=(stop_event,),
        name="scdip-notification-worker",
        daemon=True,
    )

    logger.info("Démarrage du worker de notifications...")

    worker_thread.start()

    app.state.notification_worker = worker_thread

    try:
        yield

    finally:
        logger.info("Arrêt du worker de notifications demandé...")

        stop_event.set()

        # Attend la fin du traitement en cours sans bloquer
        # la boucle asynchrone de FastAPI.
        await asyncio.to_thread(worker_thread.join, 30)

        if worker_thread.is_alive():
            logger.error(
                "Le worker n'a pas terminé dans le délai prévu."
            )
        else:
            logger.info("Worker de notifications arrêté proprement.")


app = FastAPI(
    title="SCDIP - PNLP",
    description="API de collecte des données individuelles du paludisme",
    version="0.1.0",
    lifespan=lifespan,
)


# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://scdip-pnlp.vercel.app",
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
app.include_router(rapports_router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "application": "SCDIP-PNLP",
    }
