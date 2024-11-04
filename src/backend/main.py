from fastapi import FastAPI, HTTPException
from httpx import AsyncClient
from config import settings

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello, world!"}

@app.get("/zap/status")
async def zap_status():
    """Endpoint to check ZAP status by calling its API."""
    async with AsyncClient() as client:
        try:
            response = await client.get(f"{settings.ZAP_BASE_URL}/JSON/core/view/version/")
            response.raise_for_status()
            return {"zap_version": response.json()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/zap/start-scan")
async def zap_start_scan(url: str):
    """Endpoint to start an active scan on the specified URL."""
    async with AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.ZAP_BASE_URL}/JSON/ascan/action/scan/",
                params={"url": url, "apikey": settings.ZAP_API_KEY}
            )
            response.raise_for_status()
            return {"scan_id": response.json()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
