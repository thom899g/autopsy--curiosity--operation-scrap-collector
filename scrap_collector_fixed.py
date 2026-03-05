"""
CURIOSITY: Operation Scrap Collector - Fixed Version
Robust web scraping system with comprehensive error handling and Firebase integration.
"""
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientError
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import firestore, credentials
from urllib.parse import urlparse, urljoin
import hashlib
import backoff

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ScrapingStatus(Enum):
    """Status enumeration for scraping operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class ScrapingJob:
    """Data class for scraping job configuration."""
    url: str
    max_depth: int = 3
    selectors: Dict[str, str] = None
    metadata: Dict[str, Any] = None
    job_id: str = None
    
    def __post_init__(self):
        if self.selectors is None:
            self.selectors = {"default": "body"}
        if self.metadata is None:
            self.metadata = {}
        if self.job_id is None:
            self.job_id = hashlib.md5(self.url.encode()).hexdigest()[:12]

@dataclass
class ScrapedData:
    """Data class for structured scraped content."""
    url: str
    content: Dict[str, Any]
    timestamp: datetime
    status: ScrapingStatus
    error_message: Optional[str] = None
    depth: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Firebase storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['status'] = self.status.value
        return data

class FirebaseManager:
    """Manages Firebase connection and operations."""
    
    def __init__(self, cred_path: str = None):
        self.db = None
        self.initialized = False
        self.cred_path = cred_path
        
    def initialize(self) -> bool:
        """Initialize Firebase connection."""
        try:
            if not firebase_admin._apps:
                if self.cred_path:
                    cred = credentials.Certificate(self.cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    # Try service account from environment
                    firebase_admin.initialize_app()
            
            self.db = firestore.client()
            self.initialized = True
            logger.info("Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False
    
    def save_scraped_data(self, collection: str, data: ScrapedData) -> bool:
        """Save scraped data to Firestore."""
        if not self.initialized:
            logger.error("Firebase not initialized")
            return False
        
        try:
            doc_ref = self.db.collection(collection).document(data.job_id if hasattr(data, 'job_id') else data.url)
            doc_ref.set(data.to_dict())
            logger.info(f"Saved data for {data.url} to Firestore")
            return