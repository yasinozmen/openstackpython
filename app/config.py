from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # OpenStack Credentials
    OS_AUTH_URL: str
    OS_PROJECT_NAME: str
    OS_USERNAME: str
    OS_PASSWORD: str
    OS_USER_DOMAIN_NAME: str = "Default"
    OS_PROJECT_DOMAIN_NAME: str = "Default"
    OS_IDENTITY_API_VERSION: str = "3"
    
    # FastAPI Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()