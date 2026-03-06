from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
from datetime import datetime

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")
        self.status = "idle"
        self.last_activity = datetime.now()
    
    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's main task"""
        pass
    
    def log_activity(self, message: str, level: str = "info"):
        """Log agent activity"""
        self.last_activity = datetime.now()
        getattr(self.logger, level)(f"[{self.name}] {message}")
    
    def update_status(self, status: str):
        """Update agent status"""
        self.status = status
        self.log_activity(f"Status changed to: {status}")