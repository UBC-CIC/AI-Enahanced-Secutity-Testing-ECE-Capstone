import os

class Settings:
    # Acceptable to commit this base url since this is internal IP address
    ZAP_BASE_URL = os.getenv("ZAP_BASE_URL", "http://zap-service:8080")  

settings = Settings()
