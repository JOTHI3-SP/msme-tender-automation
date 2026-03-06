import sqlite3
import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.schemas import Tender, UserProfile, EligibilityResult
import logging

class TenderDatabase:
    def __init__(self, db_path: str = "tender_system.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("database")
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create tenders table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tenders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tender_id TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        portal TEXT NOT NULL,
                        category TEXT,
                        sector TEXT,
                        deadline DATETIME NOT NULL,
                        estimated_value REAL,
                        requirements TEXT,  -- JSON string
                        status TEXT NOT NULL,
                        eligibility_result TEXT,  -- JSON string
                        documents_url TEXT,
                        document_path TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create user_profiles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_name TEXT NOT NULL,
                        annual_turnover REAL NOT NULL,
                        experience_years INTEGER NOT NULL,
                        location TEXT NOT NULL,
                        state TEXT,
                        business_sectors TEXT,  -- JSON array
                        iso_certifications TEXT,  -- JSON array
                        other_certifications TEXT,  -- JSON array
                        contact_number TEXT,
                        email TEXT,
                        pan_number TEXT,
                        gst_number TEXT,
                        msme_registration TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create search_history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS search_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        search_keyword TEXT NOT NULL,
                        results_count INTEGER,
                        search_date DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
    
    def save_tender(self, tender: Tender) -> bool:
        """Save or update tender in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert complex objects to JSON
                requirements_json = json.dumps(tender.requirements.dict()) if tender.requirements else None
                eligibility_json = json.dumps(tender.eligibility_result.dict()) if tender.eligibility_result else None
                
                cursor.execute("""
                    INSERT OR REPLACE INTO tenders 
                    (tender_id, title, description, portal, category, sector, deadline, 
                     estimated_value, requirements, status, eligibility_result, 
                     documents_url, document_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tender.tender_id,
                    tender.title,
                    tender.description,
                    tender.portal,
                    tender.category,
                    tender.sector,
                    tender.deadline.isoformat(),
                    tender.estimated_value,
                    requirements_json,
                    tender.status.value,
                    eligibility_json,
                    tender.documents_url,
                    tender.document_path,
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                self.logger.info(f"Saved tender: {tender.tender_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving tender: {e}")
            return False
    
    def get_tender(self, tender_id: str) -> Optional[Tender]:
        """Get tender by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tenders WHERE tender_id = ?", (tender_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_tender(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting tender: {e}")
            return None
    
    def get_recent_tenders(self, limit: int = 10) -> List[Tender]:
        """Get recent tenders"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tenders 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                return [self._row_to_tender(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Error getting recent tenders: {e}")
            return []
    
    def search_tenders(self, keyword: str, limit: int = 20) -> List[Tender]:
        """Search tenders by keyword"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tenders 
                    WHERE title LIKE ? OR description LIKE ? OR category LIKE ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit))
                
                rows = cursor.fetchall()
                return [self._row_to_tender(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Error searching tenders: {e}")
            return []
    
    def save_user_profile(self, profile: UserProfile) -> bool:
        """Save user profile"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear existing profiles (assuming single user for now)
                cursor.execute("DELETE FROM user_profiles")
                
                cursor.execute("""
                    INSERT INTO user_profiles 
                    (company_name, annual_turnover, experience_years, location, state,
                     business_sectors, iso_certifications, other_certifications,
                     contact_number, email, pan_number, gst_number, msme_registration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile.company_name,
                    profile.annual_turnover,
                    profile.experience_years,
                    profile.location,
                    getattr(profile, 'state', ''),
                    json.dumps(profile.business_sectors),
                    json.dumps(profile.iso_certifications),
                    json.dumps(getattr(profile, 'other_certifications', [])),
                    profile.contact_number,
                    profile.email,
                    profile.pan_number,
                    profile.gst_number,
                    getattr(profile, 'msme_registration', '')
                ))
                
                conn.commit()
                self.logger.info("User profile saved")
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving user profile: {e}")
            return False
    
    def get_user_profile(self) -> Optional[UserProfile]:
        """Get user profile"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_profiles ORDER BY created_at DESC LIMIT 1")
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_profile(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting user profile: {e}")
            return None
    
    def save_search_history(self, keyword: str, results_count: int) -> bool:
        """Save search history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO search_history (search_keyword, results_count)
                    VALUES (?, ?)
                """, (keyword, results_count))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving search history: {e}")
            return False
    
    def _row_to_tender(self, row) -> Tender:
        """Convert database row to Tender object"""
        from models.schemas import TenderRequirement, TenderStatus
        
        # Parse JSON fields
        requirements = None
        if row[8]:  # requirements column
            req_data = json.loads(row[8])
            requirements = TenderRequirement(**req_data)
        
        eligibility_result = None
        if row[10]:  # eligibility_result column
            elig_data = json.loads(row[10])
            eligibility_result = EligibilityResult(**elig_data)
        
        return Tender(
            tender_id=row[1],
            title=row[2],
            description=row[3] or "",
            portal=row[4],
            category=row[5] or "",
            sector=row[6],
            deadline=datetime.fromisoformat(row[7]),
            estimated_value=row[8],
            requirements=requirements or TenderRequirement(),
            status=TenderStatus(row[9]),
            eligibility_result=eligibility_result,
            documents_url=row[11],
            document_path=row[12],
            created_at=datetime.fromisoformat(row[13]) if row[13] else datetime.now(),
            updated_at=datetime.fromisoformat(row[14]) if row[14] else datetime.now()
        )
    
    def _row_to_profile(self, row) -> UserProfile:
        """Convert database row to UserProfile object"""
        return UserProfile(
            company_name=row[1],
            annual_turnover=row[2],
            experience_years=row[3],
            location=row[4],
            state=row[5] or "",
            business_sectors=json.loads(row[6]) if row[6] else [],
            iso_certifications=json.loads(row[7]) if row[7] else [],
            other_certifications=json.loads(row[8]) if row[8] else [],
            contact_number=row[9] or "",
            email=row[10] or "",
            pan_number=row[11] or "",
            gst_number=row[12] or "",
            msme_registration=row[13] or ""
        )