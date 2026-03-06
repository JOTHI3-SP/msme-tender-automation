from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TenderStatus(str, Enum):
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    BID_PREPARED = "bid_prepared"
    SUBMITTED = "submitted"
    CAPTCHA_REQUIRED = "captcha_required"

class EligibilityStatus(str, Enum):
    ELIGIBLE = "Eligible"
    NOT_ELIGIBLE = "Not Eligible"
    PARTIALLY_ELIGIBLE = "Partially Eligible"

class UserProfile(BaseModel):
    """MSME Company Profile for Eligibility Matching"""
    company_name: str
    annual_turnover: float  # in lakhs
    experience_years: int
    location: str
    state: str
    business_sectors: List[str] = []  # e.g., ["pump manufacturing", "textile machinery"]
    iso_certifications: List[str] = []  # e.g., ["ISO 9001:2015", "ISO 14001:2015"]
    other_certifications: List[str] = []
    contact_number: str
    email: str
    pan_number: str
    gst_number: str
    msme_registration: Optional[str] = None
    
    # MSME/Startup status
    is_msme: bool = True  # Default to MSME
    is_startup: bool = False
    
    # Financial capabilities
    can_pay_emd: bool = True  # Can provide EMD
    max_emd_amount: Optional[float] = None  # Maximum EMD amount in lakhs

class TenderRequirement(BaseModel):
    """Extracted Eligibility Requirements from Tender Documents"""
    min_turnover: Optional[float] = None  # in lakhs
    min_experience: Optional[int] = None  # in years
    required_location: Optional[str] = None
    required_state: Optional[str] = None
    required_certifications: List[str] = []
    sector_restrictions: List[str] = []
    technical_specs: Dict[str, Any] = {}
    geographic_restrictions: List[str] = []
    
    # EMD and ePBG requirements
    emd_required: bool = False
    emd_amount: Optional[float] = None  # in lakhs
    epbg_required: bool = False
    epbg_percentage: Optional[float] = None
    
    # MSME/Startup relaxations
    msme_relaxation: bool = False
    startup_relaxation: bool = False
    relaxation_note: Optional[str] = None

class EligibilityResult(BaseModel):
    """Result of Eligibility Evaluation"""
    status: EligibilityStatus
    match_score: float = Field(ge=0, le=100)  # 0-100%
    reasons: List[str] = []  # Explanation for the decision
    met_criteria: List[str] = []
    missing_criteria: List[str] = []
    gaps: List[str] = []  # What needs to be improved
    recommendations: List[str] = []  # Suggested actions

class Tender(BaseModel):
    """Government Tender Information"""
    tender_id: str
    title: str
    description: str
    portal: str  # "gem" or "cppp"
    category: str
    sector: Optional[str] = None  # pump, textile, etc.
    deadline: datetime
    estimated_value: Optional[float] = None
    requirements: TenderRequirement
    status: TenderStatus = TenderStatus.DISCOVERED
    eligibility_result: Optional[EligibilityResult] = None
    documents_url: Optional[str] = None
    document_path: Optional[str] = None  # Local path to downloaded PDF
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class BidDocument(BaseModel):
    """Generated Bid Documents"""
    tender_id: str
    document_type: str  # "eoi", "technical", "financial"
    content: str
    attachments: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    approved_by_user: bool = False

class CaptchaRequest(BaseModel):
    """CAPTCHA Alert for Human Intervention"""
    session_id: str
    tender_id: str
    portal: str
    screenshot_path: str
    message: str
    whatsapp_sent: bool = False
    resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

class UserQuery(BaseModel):
    """User Query for Tender Information"""
    query: str
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class AgentResponse(BaseModel):
    """Agent Response to User Queries"""
    response: str
    confidence: float
    sources: List[str] = []
    suggested_actions: List[str] = []
    tender_references: List[str] = []  # Referenced tender IDs

class NotificationMessage(BaseModel):
    """Notification Message for WhatsApp/UI"""
    message: str
    priority: str = "normal"  # low, normal, high, critical
    channels: List[str] = ["whatsapp", "ui"]  # notification channels
    tender_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    delivered: bool = False