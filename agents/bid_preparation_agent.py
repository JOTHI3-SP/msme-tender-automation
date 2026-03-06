import asyncio
from typing import Dict, Any, Optional
from groq import Groq
import os
from agents.base_agent import BaseAgent
from models.schemas import Tender, BidDocument, TenderStatus
from database.database import TenderDatabase
from services.notification_service import NotificationService
from config.settings import settings
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class BidPreparationAgent(BaseAgent):
    def __init__(self):
        super().__init__("BidPreparation")
        self.db = TenderDatabase()
        self.notification_service = NotificationService()
        
        # Configure Groq
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key:
            self.groq_client = Groq(api_key=groq_api_key)
            self.log_activity("Groq client initialized for bid preparation")
        else:
            self.groq_client = None
            self.log_activity("No Groq API key found - bid preparation will be limited", "warning")
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare bid documents for eligible tenders"""
        self.update_status("preparing")
        
        try:
            tender_id = task.get("tender_id")
            if not tender_id:
                return {"status": "error", "message": "No tender_id provided"}
            
            # Get tender data
            tenders = self.db.get_tenders()
            tender_data = next((t for t in tenders if t["tender_id"] == tender_id), None)
            
            if not tender_data:
                return {"status": "error", "message": "Tender not found"}
            
            # Check if tender is eligible
            if tender_data.get("eligibility_score", 0) < 70:
                return {"status": "error", "message": "Tender not eligible for bidding"}
            
            # Get user profile
            user_profile = self.db.get_user_profile()
            if not user_profile:
                return {"status": "error", "message": "User profile not found"}
            
            self.log_activity(f"Preparing bid for tender: {tender_data['title']}")
            
            # Generate bid documents
            bid_result = await self.generate_bid_documents(tender_data, user_profile)
            
            if bid_result["success"]:
                # Update tender status
                tender_data["status"] = TenderStatus.BID_PREPARED.value
                
                tender = Tender(**{
                    **tender_data,
                    "deadline": datetime.fromisoformat(tender_data["deadline"]),
                    "requirements": json.loads(tender_data["requirements"]) if tender_data["requirements"] else {},
                    "status": TenderStatus.BID_PREPARED
                })
                
                self.db.save_tender(tender)
                
                # Send notification
                await self.notification_service.send_bid_ready_alert(
                    tender, 
                    bid_result["summary"]
                )
                
                self.update_status("idle")
                self.log_activity(f"Bid prepared successfully for {tender_id}")
                
                return {
                    "status": "success",
                    "tender_id": tender_id,
                    "bid_documents": bid_result["documents"],
                    "summary": bid_result["summary"]
                }
            else:
                return {"status": "error", "message": bid_result["error"]}
                
        except Exception as e:
            self.update_status("error")
            self.log_activity(f"Error preparing bid: {str(e)}", "error")
            return {"status": "error", "message": str(e)}
    
    async def generate_bid_documents(self, tender_data: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate bid documents using AI"""
        try:
            documents = []
            
            # Generate Expression of Interest (EOI)
            eoi_result = await self.generate_eoi(tender_data, user_profile)
            if eoi_result["success"]:
                documents.append(eoi_result["document"])
            
            # Generate Technical Proposal
            technical_result = await self.generate_technical_proposal(tender_data, user_profile)
            if technical_result["success"]:
                documents.append(technical_result["document"])
            
            # Generate Financial Proposal
            financial_result = await self.generate_financial_proposal(tender_data, user_profile)
            if financial_result["success"]:
                documents.append(financial_result["document"])
            
            # Generate bid summary
            summary = await self.generate_bid_summary(tender_data, user_profile, documents)
            
            return {
                "success": True,
                "documents": documents,
                "summary": summary
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_eoi(self, tender_data: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Expression of Interest document"""
        try:
            if not self.groq_client:
                return {"success": False, "error": "Groq client not available"}
            
            prompt = f"""
            Generate a professional Expression of Interest (EOI) document for the following tender:
            
            TENDER DETAILS:
            Title: {tender_data['title']}
            Description: {tender_data['description']}
            Category: {tender_data['category']}
            Portal: {tender_data['portal'].upper()}
            Deadline: {tender_data['deadline']}
            
            COMPANY DETAILS:
            Company Name: {user_profile['company_name']}
            Experience: {user_profile['experience_years']} years
            Annual Turnover: Rs. {user_profile['turnover']} Lakhs
            Location: {user_profile['location']}
            Contact: {user_profile['contact_number']}
            Email: {user_profile['email']}
            PAN: {user_profile['pan_number']}
            GST: {user_profile['gst_number']}
            
            Generate a formal EOI document with:
            1. Company introduction
            2. Relevant experience
            3. Technical capabilities
            4. Commitment statement
            5. Contact information
            
            Keep it professional and concise (max 500 words).
            """
            
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.3,
                max_tokens=1000
            )
            
            eoi_content = response.choices[0].message.content
            
            # Save EOI document
            eoi_document = BidDocument(
                tender_id=tender_data["tender_id"],
                document_type="eoi",
                content=eoi_content,
                attachments=[]
            )
            
            return {
                "success": True,
                "document": eoi_document.dict()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_technical_proposal(self, tender_data: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Technical Proposal document"""
        try:
            if not self.groq_client:
                return {"success": False, "error": "Groq client not available"}
            
            requirements = json.loads(tender_data.get("requirements", "{}"))
            
            prompt = f"""
            Generate a technical proposal for the following tender:
            
            TENDER: {tender_data['title']}
            REQUIREMENTS: {json.dumps(requirements, indent=2)}
            
            COMPANY CAPABILITIES:
            - Experience: {user_profile['experience_years']} years
            - Technical Capabilities: {user_profile.get('technical_capabilities', [])}
            - Certifications: {user_profile.get('iso_certifications', [])}
            
            Generate a technical proposal covering:
            1. Understanding of requirements
            2. Technical approach
            3. Quality assurance measures
            4. Timeline and milestones
            5. Risk mitigation
            
            Keep it detailed but concise (max 800 words).
            """
            
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.3,
                max_tokens=1500
            )
            
            technical_content = response.choices[0].message.content
            
            # Save technical document
            technical_document = BidDocument(
                tender_id=tender_data["tender_id"],
                document_type="technical",
                content=technical_content,
                attachments=[]
            )
            
            return {
                "success": True,
                "document": technical_document.dict()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_financial_proposal(self, tender_data: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Financial Proposal document"""
        try:
            if not self.groq_client:
                return {"success": False, "error": "Groq client not available"}
            
            estimated_value = tender_data.get("estimated_value", 0)
            
            prompt = f"""
            Generate a financial proposal for the following tender:
            
            TENDER: {tender_data['title']}
            ESTIMATED VALUE: Rs. {estimated_value} Lakhs
            
            COMPANY DETAILS:
            - Annual Turnover: Rs. {user_profile['turnover']} Lakhs
            - GST Number: {user_profile['gst_number']}
            - PAN Number: {user_profile['pan_number']}
            
            Generate a financial proposal with:
            1. Cost breakdown
            2. Payment terms
            3. Tax implications
            4. Performance guarantee
            5. Validity period
            
            Make it competitive but profitable (max 400 words).
            """
            
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.3,
                max_tokens=800
            )
            
            financial_content = response.choices[0].message.content
            
            # Save financial document
            financial_document = BidDocument(
                tender_id=tender_data["tender_id"],
                document_type="financial",
                content=financial_content,
                attachments=[]
            )
            
            return {
                "success": True,
                "document": financial_document.dict()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_bid_summary(self, tender_data: Dict[str, Any], user_profile: Dict[str, Any], documents: list) -> str:
        """Generate bid summary for user review"""
        try:
            summary = f"""
BID SUMMARY

Tender: {tender_data['title']}
Portal: {tender_data['portal'].upper()}
Deadline: {tender_data['deadline']}
Eligibility Score: {tender_data.get('eligibility_score', 0)}%

Company: {user_profile['company_name']}
Contact: {user_profile['contact_number']}

Documents Prepared:
"""
            
            for doc in documents:
                doc_type = doc['document_type'].upper()
                word_count = len(doc['content'].split())
                summary += f"• {doc_type}: {word_count} words\n"
            
            summary += f"""
Status: Ready for review and submission
Next Step: Human approval required

IMPORTANT: Please review all documents before approving submission.
            """
            
            return summary
            
        except Exception as e:
            return f"Error generating summary: {str(e)}"