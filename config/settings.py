import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    google_api_key: str
    green_api_instance_id: str
    green_api_access_token: str
    user_whatsapp_number: str
    
    # Database
    database_url: str = "sqlite:///./tender_system.db"
    
    # Portal URLs
    gem_portal_url: str = "https://gem.gov.in"
    cppp_portal_url: str = "https://eprocure.gov.in"
    
    # System Settings
    monitoring_interval_hours: int = 24
    max_concurrent_agents: int = 5
    session_timeout_minutes: int = 30
    
    # File Paths
    downloads_dir: str = "downloads"
    temp_dir: str = "temp"
    logs_dir: str = "logs"
    
    class Config:
        env_file = ".env"

settings = Settings()