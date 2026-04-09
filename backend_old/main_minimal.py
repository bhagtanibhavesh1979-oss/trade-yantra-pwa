from fastapi import FastAPI
import uvicorn
from services.angel_service import angel_service
from services.websocket_manager import ws_manager

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("==> Trade Yantra Backend Starting...")
    # threading.Thread(target=angel_service.load_scrip_master, daemon=True).start()
    print("==> Backend Ready!")
    yield
    print("==> Trade Yantra Backend Shutting Down...")
    ws_manager.stop_all()

app = FastAPI(lifespan=lifespan)

from routes import auth, stream
app.include_router(auth.router)
app.include_router(stream.router)

@app.get("/")
def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
