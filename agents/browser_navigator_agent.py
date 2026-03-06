import asyncio
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from agents.base_agent import BaseAgent
from models.schemas import CaptchaRequest
from database.database import TenderDatabase
from services.notification_service import NotificationService
import uuid
import os
from datetime import datetime

class BrowserNavigatorAgent(BaseAgent):
    def __init__(self):
        super().__init__("BrowserNavigator")
        self.db = TenderDatabase()
        self.notification_service = NotificationService()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.session_id = str(uuid.uuid4())
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate portal and fill forms"""
        self.update_status("navigating")
        
        try:
            action = task.get("action")
            tender_id = task.get("tender_id")
            
            if action == "fill_form":
                return await self.fill_tender_form(tender_id)
            elif action == "download_documents":
                return await self.download_tender_documents(tender_id)
            else:
                return {"status": "error", "message": "Unknown action"}
                
        except Exception as e:
            self.update_status("error")
            self.log_activity(f"Error in browser navigation: {str(e)}", "error")
            return {"status": "error", "message": str(e)}
    
    async def fill_tender_form(self, tender_id: str) -> Dict[str, Any]:
        """Fill tender form with user data"""
        try:
            # Get tender data
            tenders = self.db.get_tenders()
            tender_data = next((t for t in tenders if t["tender_id"] == tender_id), None)
            
            if not tender_data:
                return {"status": "error", "message": "Tender not found"}
            
            # Get user profile
            user_profile = self.db.get_user_profile()
            if not user_profile:
                return {"status": "error", "message": "User profile not found"}
            
            self.log_activity(f"Filling form for tender: {tender_data['title']}")
            
            # Initialize browser
            await self.init_browser()
            
            # Navigate to portal
            portal_url = self.get_portal_url(tender_data["portal"])
            await self.page.goto(portal_url)
            
            # Handle login if required
            login_result = await self.handle_login(tender_data["portal"])
            if not login_result["success"]:
                return login_result
            
            # Navigate to tender form
            form_result = await self.navigate_to_tender_form(tender_id, tender_data)
            if not form_result["success"]:
                return form_result
            
            # Fill form fields
            fill_result = await self.fill_form_fields(user_profile)
            if not fill_result["success"]:
                return fill_result
            
            # Handle document upload
            upload_result = await self.upload_documents(user_profile)
            if not upload_result["success"]:
                return upload_result
            
            self.update_status("idle")
            self.log_activity(f"Successfully filled form for {tender_id}")
            
            return {
                "status": "success",
                "tender_id": tender_id,
                "message": "Form filled successfully, ready for submission"
            }
            
        except Exception as e:
            self.log_activity(f"Error filling form: {str(e)}", "error")
            return {"status": "error", "message": str(e)}
        finally:
            await self.cleanup_browser()
    
    async def init_browser(self):
        """Initialize browser and page"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        self.page = await context.new_page()
        
        # Set longer timeouts
        self.page.set_default_timeout(30000)
    
    async def handle_login(self, portal: str) -> Dict[str, Any]:
        """Handle portal login"""
        try:
            # Check if login is required
            login_selectors = [
                "input[type='email']",
                "input[name='username']",
                "input[name='login']",
                ".login-form"
            ]
            
            login_required = False
            for selector in login_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    login_required = True
                    break
                except:
                    continue
            
            if not login_required:
                return {"success": True, "message": "No login required"}
            
            # For demo purposes, we'll simulate login
            # In real implementation, you would handle actual login
            self.log_activity("Login required - simulating login process")
            
            # Check for CAPTCHA during login
            captcha_result = await self.check_for_captcha("login")
            if captcha_result["captcha_found"]:
                return {"success": False, "message": "CAPTCHA required for login", "captcha_required": True}
            
            return {"success": True, "message": "Login successful"}
            
        except Exception as e:
            return {"success": False, "message": f"Login failed: {str(e)}"}
    
    async def navigate_to_tender_form(self, tender_id: str, tender_data: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate to specific tender form"""
        try:
            # Search for tender
            search_selectors = [
                "input[name='search']",
                "input[type='search']",
                ".search-input"
            ]
            
            for selector in search_selectors:
                try:
                    search_input = await self.page.wait_for_selector(selector, timeout=5000)
                    await search_input.fill(tender_data["title"][:50])  # Use first 50 chars
                    await search_input.press("Enter")
                    break
                except:
                    continue
            
            # Wait for search results
            await self.page.wait_for_load_state("networkidle")
            
            # Click on tender link
            tender_link_selectors = [
                f"a[href*='{tender_id}']",
                ".tender-link",
                ".tender-title a"
            ]
            
            for selector in tender_link_selectors:
                try:
                    tender_link = await self.page.wait_for_selector(selector, timeout=5000)
                    await tender_link.click()
                    break
                except:
                    continue
            
            # Wait for tender form to load
            await self.page.wait_for_load_state("networkidle")
            
            return {"success": True, "message": "Navigated to tender form"}
            
        except Exception as e:
            return {"success": False, "message": f"Navigation failed: {str(e)}"}
    
    async def fill_form_fields(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Fill form fields with user data"""
        try:
            # Common form field mappings
            field_mappings = {
                "company_name": ["input[name*='company']", "input[name*='organization']", "input[name*='firm']"],
                "contact_number": ["input[name*='phone']", "input[name*='mobile']", "input[name*='contact']"],
                "email": ["input[name*='email']", "input[type='email']"],
                "pan_number": ["input[name*='pan']", "input[name*='PAN']"],
                "gst_number": ["input[name*='gst']", "input[name*='GST']", "input[name*='gstin']"],
                "location": ["input[name*='address']", "input[name*='location']", "input[name*='city']"]
            }
            
            filled_fields = 0
            
            for field_name, selectors in field_mappings.items():
                field_value = user_profile.get(field_name, "")
                if not field_value:
                    continue
                
                for selector in selectors:
                    try:
                        field_element = await self.page.wait_for_selector(selector, timeout=3000)
                        await field_element.fill(str(field_value))
                        filled_fields += 1
                        self.log_activity(f"Filled {field_name}: {field_value}")
                        break
                    except:
                        continue
            
            # Check for CAPTCHA after filling fields
            captcha_result = await self.check_for_captcha("form_filling")
            if captcha_result["captcha_found"]:
                return {"success": False, "message": "CAPTCHA required", "captcha_required": True}
            
            return {"success": True, "message": f"Filled {filled_fields} form fields"}
            
        except Exception as e:
            return {"success": False, "message": f"Form filling failed: {str(e)}"}
    
    async def upload_documents(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Upload required documents"""
        try:
            # Look for file upload inputs
            upload_selectors = [
                "input[type='file']",
                ".file-upload",
                ".document-upload"
            ]
            
            uploaded_count = 0
            
            for selector in upload_selectors:
                try:
                    upload_elements = await self.page.query_selector_all(selector)
                    
                    for upload_element in upload_elements:
                        # For demo purposes, we'll simulate document upload
                        # In real implementation, you would upload actual documents
                        self.log_activity("Document upload field found - would upload documents here")
                        uploaded_count += 1
                        
                except:
                    continue
            
            return {"success": True, "message": f"Found {uploaded_count} upload fields"}
            
        except Exception as e:
            return {"success": False, "message": f"Document upload failed: {str(e)}"}
    
    async def check_for_captcha(self, context: str) -> Dict[str, Any]:
        """Check for CAPTCHA and handle human intervention"""
        try:
            captcha_selectors = [
                ".captcha",
                "#captcha",
                "img[src*='captcha']",
                ".recaptcha",
                ".g-recaptcha"
            ]
            
            captcha_found = False
            captcha_element = None
            
            for selector in captcha_selectors:
                try:
                    captcha_element = await self.page.wait_for_selector(selector, timeout=2000)
                    captcha_found = True
                    break
                except:
                    continue
            
            if captcha_found:
                self.log_activity(f"CAPTCHA detected during {context}")
                
                # Take screenshot
                screenshot_path = f"temp/captcha_{self.session_id}_{int(datetime.now().timestamp())}.png"
                os.makedirs("temp", exist_ok=True)
                await self.page.screenshot(path=screenshot_path)
                
                # Create CAPTCHA request
                captcha_request = CaptchaRequest(
                    session_id=self.session_id,
                    tender_id="current_tender",
                    portal="current_portal",
                    screenshot_path=screenshot_path,
                    message=f"CAPTCHA required during {context}"
                )
                
                # Send notification
                await self.notification_service.send_captcha_alert(captcha_request)
                
                # Wait for human intervention (in real implementation)
                self.log_activity("Waiting for human to solve CAPTCHA...")
                await asyncio.sleep(5)  # Simulate waiting
                
                return {"captcha_found": True, "screenshot_path": screenshot_path}
            
            return {"captcha_found": False}
            
        except Exception as e:
            self.log_activity(f"Error checking CAPTCHA: {str(e)}", "error")
            return {"captcha_found": False, "error": str(e)}
    
    def get_portal_url(self, portal: str) -> str:
        """Get portal URL"""
        urls = {
            "gem": "https://gem.gov.in",
            "cppp": "https://eprocure.gov.in"
        }
        return urls.get(portal, "https://gem.gov.in")
    
    async def cleanup_browser(self):
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            self.log_activity(f"Error cleaning up browser: {str(e)}", "error")