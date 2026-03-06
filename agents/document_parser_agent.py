import asyncio
import os
from typing import Dict, Any, List
import PyPDF2
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re
import json
from agents.base_agent import BaseAgent
from models.schemas import TenderRequirement
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DocumentParserAgent(BaseAgent):
    def __init__(self):
        super().__init__("DocumentParser")
        
        # Initialize Groq client
        self.groq_client = None
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_api_key)
                self.log_activity("Groq client initialized successfully")
            except Exception as e:
                self.log_activity(f"Failed to initialize Groq client: {e}", "warning")
        
        if not self.groq_client:
            self.log_activity("No Groq API key found - will use rule-based parsing only", "warning")
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute document parsing task"""
        try:
            self.update_status("parsing")
            
            document_path = task.get("document_path")
            if not document_path:
                return {
                    "status": "error",
                    "error": "No document path provided"
                }
            
            if not os.path.exists(document_path):
                return {
                    "status": "error",
                    "error": f"Document not found: {document_path}"
                }
            
            self.log_activity(f"Parsing document: {document_path}")
            
            # Extract text from PDF
            text_content = await self.extract_pdf_text(document_path)
            
            if not text_content:
                return {
                    "status": "error",
                    "error": "Failed to extract text from document"
                }
            
            self.log_activity(f"Extracted {len(text_content)} characters of text")
            
            # Parse eligibility requirements using Groq
            requirements = await self.parse_eligibility_requirements(text_content)
            
            return {
                "status": "success",
                "requirements": requirements,
                "text_content": text_content[:1000]  # First 1000 chars for debugging
            }
            
        except Exception as e:
            self.log_activity(f"Error in document parsing: {e}", "error")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF using PyMuPDF"""
        try:
            text_content = ""
            
            # Use PyMuPDF for better text extraction
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_content += page.get_text()
            
            doc.close()
            
            return text_content.strip()
            
        except Exception as e:
            self.log_activity(f"Error extracting PDF text: {e}", "error")
            return ""
    
    async def parse_eligibility_requirements(self, text_content: str) -> TenderRequirement:
        """Parse eligibility requirements using Groq AI"""
        try:
            if not self.groq_client:
                return await self.parse_requirements_fallback(text_content)
            
            # Clean and prepare text for analysis
            cleaned_text = self.clean_text_for_analysis(text_content)
            
            prompt = f"""
            Analyze this GeM tender document and extract ONLY the specific eligibility requirements for companies/MSMEs.
            
            The document contains mixed Hindi/English text. Focus on sections about:
            1. Minimum annual turnover (look for "turnover", "टर्नओवर")
            2. Years of experience required (look for "experience", "अनुभव")
            3. Required certifications (ISO, BIS, etc.)
            4. Location restrictions
            5. MSME/Startup relaxations (look for "MSE Relaxation", "Startup Relaxation")
            6. EMD requirements (look for "EMD", "Earnest Money")
            7. ePBG requirements (look for "ePBG", "Performance Bank Guarantee")
            
            Document text:
            {cleaned_text[:6000]}
            
            IMPORTANT: If MSE/MSME relaxation is mentioned as "Yes" or available, then turnover and experience requirements should be null/relaxed.
            
            Extract ONLY concrete requirements. If no specific requirement is mentioned, return null.
            
            Respond in JSON format:
            {{
                "min_turnover": <number in lakhs or null if MSME relaxation applies>,
                "min_experience": <number in years or null if MSME relaxation applies>,
                "required_location": "<specific location or null>",
                "required_state": "<specific state or null>",
                "required_certifications": ["specific cert names"],
                "sector_restrictions": ["specific sectors only"],
                "emd_required": <true/false>,
                "emd_amount": <amount in lakhs or null>,
                "epbg_required": <true/false>,
                "epbg_percentage": <percentage or null>,
                "msme_relaxation": <true/false>,
                "startup_relaxation": <true/false>,
                "relaxation_note": "<explanation if relaxation applies>"
            }}
            """
            
            response = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.1-8b-instant",
                temperature=0.1,
                max_tokens=800
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                requirements_data = json.loads(json_match.group())
                
                requirements = TenderRequirement(
                    min_turnover=requirements_data.get("min_turnover"),
                    min_experience=requirements_data.get("min_experience"),
                    required_location=requirements_data.get("required_location"),
                    required_state=requirements_data.get("required_state"),
                    required_certifications=requirements_data.get("required_certifications", []),
                    sector_restrictions=requirements_data.get("sector_restrictions", []),
                    emd_required=requirements_data.get("emd_required", False),
                    emd_amount=requirements_data.get("emd_amount"),
                    epbg_required=requirements_data.get("epbg_required", False),
                    epbg_percentage=requirements_data.get("epbg_percentage"),
                    msme_relaxation=requirements_data.get("msme_relaxation", False),
                    startup_relaxation=requirements_data.get("startup_relaxation", False),
                    relaxation_note=requirements_data.get("relaxation_note"),
                    technical_specs={
                        "msme_relaxation": requirements_data.get("msme_relaxation", False),
                        "startup_relaxation": requirements_data.get("startup_relaxation", False)
                    }
                )
                
                self.log_activity("Successfully parsed requirements using Groq")
                return requirements
            
        except Exception as e:
            self.log_activity(f"Error using Groq for parsing: {e}", "warning")
        
        # Fallback to rule-based parsing
        return await self.parse_requirements_fallback(text_content)
    
    def clean_text_for_analysis(self, text: str) -> str:
        """Clean text for better analysis"""
        # Remove excessive whitespace and special characters
        cleaned = re.sub(r'\s+', ' ', text)
        # Remove non-printable characters except common ones
        cleaned = re.sub(r'[^\w\s\-.,():/]', ' ', cleaned)
        return cleaned.strip()
    
    async def parse_requirements_fallback(self, text_content: str) -> TenderRequirement:
        """Enhanced fallback rule-based parsing for GeM tender documents"""
        try:
            self.log_activity("Using enhanced fallback rule-based parsing")
            
            requirements = TenderRequirement()
            text_lower = text_content.lower()
            
            # Check for EMD requirements
            emd_required = False
            emd_amount = None
            if "emd" in text_lower or "earnest money" in text_lower:
                if "no emd" in text_lower or "emd: no" in text_lower or "emd required: no" in text_lower:
                    emd_required = False
                    self.log_activity("EMD not required")
                else:
                    emd_required = True
                    # Try to extract EMD amount
                    emd_patterns = [
                        r'emd.*?(\d+(?:\.\d+)?)\s*(?:lakh|lakhs)',
                        r'earnest.*money.*?(\d+(?:\.\d+)?)\s*(?:lakh|lakhs)',
                        r'emd.*?rs\.?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lakhs)'
                    ]
                    for pattern in emd_patterns:
                        match = re.search(pattern, text_lower)
                        if match:
                            emd_amount = float(match.group(1))
                            break
                    self.log_activity(f"EMD required: {emd_amount} lakhs" if emd_amount else "EMD required")
            
            requirements.emd_required = emd_required
            requirements.emd_amount = emd_amount
            
            # Check for ePBG requirements
            epbg_required = False
            epbg_percentage = None
            if "epbg" in text_lower or "performance bank guarantee" in text_lower:
                if "no epbg" in text_lower or "epbg: no" in text_lower or "epbg required: no" in text_lower:
                    epbg_required = False
                    self.log_activity("ePBG not required")
                else:
                    epbg_required = True
                    # Try to extract ePBG percentage
                    epbg_patterns = [
                        r'epbg.*?(\d+(?:\.\d+)?)\s*%',
                        r'performance.*guarantee.*?(\d+(?:\.\d+)?)\s*%'
                    ]
                    for pattern in epbg_patterns:
                        match = re.search(pattern, text_lower)
                        if match:
                            epbg_percentage = float(match.group(1))
                            break
                    self.log_activity(f"ePBG required: {epbg_percentage}%" if epbg_percentage else "ePBG required")
            
            requirements.epbg_required = epbg_required
            requirements.epbg_percentage = epbg_percentage
            
            # Check for MSME/Startup relaxations first
            msme_relaxation = False
            startup_relaxation = False
            relaxation_note = None
            
            if "mse relaxation" in text_lower or "msme relaxation" in text_lower:
                # Look for "Yes" or "No" after relaxation
                mse_context = text_lower.split("mse relaxation")[1][:100] if "mse relaxation" in text_lower else ""
                if "yes" in mse_context or "available" in mse_context:
                    msme_relaxation = True
                    relaxation_note = "MSE relaxation for years of experience and turnover available"
                    self.log_activity("MSME relaxation available - turnover and experience requirements waived")
                elif "no" in mse_context:
                    msme_relaxation = False
                    self.log_activity("MSME relaxation not available")
            
            if "startup relaxation" in text_lower:
                startup_context = text_lower.split("startup relaxation")[1][:100]
                if "yes" in startup_context or "available" in startup_context:
                    startup_relaxation = True
                    if not relaxation_note:
                        relaxation_note = "Startup relaxation for years of experience and turnover available"
                    self.log_activity("Startup relaxation available")
                elif "no" in startup_context:
                    startup_relaxation = False
                    self.log_activity("Startup relaxation not available")
            
            requirements.msme_relaxation = msme_relaxation
            requirements.startup_relaxation = startup_relaxation
            requirements.relaxation_note = relaxation_note
            
            # If relaxations are available, set turnover and experience to None
            if msme_relaxation or startup_relaxation:
                requirements.min_turnover = None
                requirements.min_experience = None
                self.log_activity("Relaxations available - turnover and experience requirements set to None")
                return requirements
            
            # Extract minimum turnover only if no relaxation
            turnover_patterns = [
                r'minimum.*turnover.*?(\d+(?:\.\d+)?)\s*(?:crore|cr)',
                r'turnover.*?(\d+(?:\.\d+)?)\s*(?:crore|cr)',
                r'annual.*turnover.*?(\d+(?:\.\d+)?)\s*(?:lakh|lakhs)',
                r'minimum.*turnover.*?rs\.?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lakhs)',
                r'financial.*capacity.*?(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh|lakhs)',
                r'turnover.*criteria.*?(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh|lakhs)'
            ]
            
            for pattern in turnover_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    value = float(match.group(1))
                    # Convert crores to lakhs
                    if 'crore' in match.group(0) or 'cr' in match.group(0):
                        value *= 100
                    requirements.min_turnover = value
                    self.log_activity(f"Found turnover requirement: {value} lakhs")
                    break
            
            # Extract minimum experience only if no relaxation
            exp_patterns = [
                r'minimum.*experience.*?(\d+)\s*years?',
                r'experience.*?(\d+)\s*years?',
                r'(\d+)\s*years?.*experience',
                r'experience.*criteria.*?(\d+)\s*years?',
                r'past.*experience.*?(\d+)\s*years?'
            ]
            
            for pattern in exp_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    requirements.min_experience = int(match.group(1))
                    self.log_activity(f"Found experience requirement: {requirements.min_experience} years")
                    break
            
            # Extract certifications - enhanced patterns for Indian standards
            cert_patterns = [
                r'iso\s*\d+(?::\d+)?',
                r'bis\s*\d+',
                r'is\s*\d+(?::\d+)?',  # Indian Standard
                r'quality\s*certification',
                r'iso\s*certification',
                r'bis\s*certification'
            ]
            
            certifications = []
            for pattern in cert_patterns:
                matches = re.findall(pattern, text_lower)
                certifications.extend(matches)
            
            if certifications:
                requirements.required_certifications = list(set(certifications))
                self.log_activity(f"Found certifications: {requirements.required_certifications}")
            
            # Extract location requirements - enhanced for Indian locations
            location_patterns = [
                r'location.*?([a-zA-Z\s]+(?:state|district|city))',
                r'registered.*?([a-zA-Z\s]+(?:state|district|city))',
                r'office.*?([a-zA-Z\s]+(?:state|district|city))',
                r'based.*?([a-zA-Z\s]+(?:state|district|city))'
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    location = match.group(1).strip()
                    if len(location) > 3:  # Valid location
                        requirements.required_location = location
                        self.log_activity(f"Found location requirement: {requirements.required_location}")
                        break
            
            # Extract item category as sector restriction
            category_patterns = [
                r'item\s*category[:\s]*([^/\n]+)',
                r'category[:\s]*([^/\n]+)',
                r'product[:\s]*([^/\n]+)'
            ]
            
            for pattern in category_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    category = match.group(1).strip()
                    if len(category) > 5 and len(category) < 100:  # Reasonable category length
                        requirements.sector_restrictions = [category]
                        self.log_activity(f"Found item category: {category}")
                        break
            
            self.log_activity("Completed enhanced fallback parsing")
            return requirements
            
        except Exception as e:
            self.log_activity(f"Error in fallback parsing: {e}", "error")
            return TenderRequirement()
    
    async def extract_key_information(self, text_content: str) -> Dict[str, Any]:
        """Extract key information from document"""
        try:
            info = {
                "tender_number": None,
                "tender_title": None,
                "deadline": None,
                "estimated_value": None,
                "department": None
            }
            
            text_lower = text_content.lower()
            
            # Extract tender number
            tender_patterns = [
                r'tender\s*no\.?\s*:?\s*([A-Z0-9/_-]+)',
                r'bid\s*no\.?\s*:?\s*([A-Z0-9/_-]+)',
                r'gem\s*/\s*(\d+\s*/\s*[A-Z]\s*/\s*\d+)'
            ]
            
            for pattern in tender_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    info["tender_number"] = match.group(1).strip()
                    break
            
            return info
            
        except Exception as e:
            self.log_activity(f"Error extracting key information: {e}", "error")
            return {}