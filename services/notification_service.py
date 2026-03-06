import asyncio
import os
import requests
from typing import Dict, Any, List
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class NotificationService:
    def __init__(self):
        self.logger = logging.getLogger("notification_service")
        
        # Green API configuration
        self.green_api_instance_id = os.getenv('GREEN_API_INSTANCE_ID')
        self.green_api_access_token = os.getenv('GREEN_API_ACCESS_TOKEN')
        self.user_whatsapp_number = os.getenv('USER_WHATSAPP_NUMBER')
        
        if self.green_api_instance_id and self.green_api_access_token:
            self.green_api_url = f"https://api.green-api.com/waInstance{self.green_api_instance_id}"
            self.whatsapp_enabled = True
            self.logger.info("Green API WhatsApp integration enabled")
        else:
            self.whatsapp_enabled = False
            self.logger.warning("Green API credentials not found - WhatsApp notifications disabled")
    
    async def send_notification(self, message: str, priority: str = "normal", send_whatsapp: bool = True) -> bool:
        """Send notification via console/UI and WhatsApp"""
        try:
            priority_emoji = {
                "low": "ℹ️",
                "normal": "📢", 
                "high": "⚠️",
                "critical": "🚨"
            }
            
            emoji = priority_emoji.get(priority, "📢")
            formatted_message = f"{emoji} {message}"
            
            # Log the notification
            self.logger.info(f"NOTIFICATION [{priority.upper()}]: {message}")
            
            # Console notification
            print(f"\n{formatted_message}\n")
            
            # Send WhatsApp notification if enabled
            if send_whatsapp and self.whatsapp_enabled and self.user_whatsapp_number:
                whatsapp_sent = await self.send_whatsapp_message(formatted_message)
                if whatsapp_sent:
                    self.logger.info("WhatsApp notification sent successfully")
                else:
                    self.logger.warning("Failed to send WhatsApp notification")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
    
    async def send_whatsapp_message(self, message: str) -> bool:
        """Send WhatsApp message using Green API"""
        try:
            if not self.whatsapp_enabled:
                self.logger.warning("WhatsApp not enabled - skipping message")
                return False
            
            url = f"{self.green_api_url}/sendMessage/{self.green_api_access_token}"
            
            # Format phone number for Green API (without + sign)
            phone_number = self.user_whatsapp_number.replace("+", "")
            
            payload = {
                "chatId": f"{phone_number}@c.us",
                "message": message
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Make async request
            response = await asyncio.to_thread(
                requests.post, url, json=payload, headers=headers, timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("idMessage"):
                    self.logger.info(f"WhatsApp message sent successfully: {result['idMessage']}")
                    return True
                else:
                    self.logger.error(f"Green API error: {result}")
                    return False
            else:
                self.logger.error(f"HTTP error: {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp message: {e}")
            return False
    
    async def send_eligibility_notification(self, tender_title: str, status: str, score: float, reasons: List[str]) -> bool:
        """Send eligibility analysis notification via WhatsApp"""
        status_emoji = "✅" if status == "Eligible" else "❌" if status == "Not Eligible" else "⚠️"
        
        message = f"""🎯 *TENDER ELIGIBILITY ANALYSIS*

{status_emoji} *Status:* {status}
📊 *Score:* {score:.1f}%

📋 *Tender:* {tender_title[:60]}...

*Key Points:*
{chr(10).join(f"• {reason}" for reason in reasons[:3])}

💡 Check the system for detailed analysis and next steps.

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "high", send_whatsapp=True)
    
    async def send_deadline_alert(self, tender_title: str, deadline: str, hours_remaining: int) -> bool:
        """Send deadline reminder via WhatsApp"""
        urgency = "critical" if hours_remaining <= 24 else "high"
        urgency_emoji = "🚨" if hours_remaining <= 24 else "⏰"
        
        message = f"""{urgency_emoji} *TENDER DEADLINE ALERT*

📋 *Tender:* {tender_title[:60]}...
⏰ *Deadline:* {deadline}
⏳ *Time Remaining:* {hours_remaining} hours

{"🚨 URGENT: Less than 24 hours remaining!" if hours_remaining <= 24 else "⚠️ Deadline approaching soon!"}

Don't miss this opportunity!

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, urgency, send_whatsapp=True)
    
    async def send_tender_discovery_alert(self, keyword: str, tender_count: int, eligible_count: int = 0) -> bool:
        """Send alert about newly discovered tenders"""
        message = f"""🔍 *NEW TENDERS FOUND*

*Search Keyword:* {keyword}
📊 *Total Found:* {tender_count} tenders
✅ *Potentially Eligible:* {eligible_count} tenders

🎯 Check the system to analyze eligibility and download documents.

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "normal", send_whatsapp=True)
    
    async def send_document_download_alert(self, tender_title: str, pdf_path: str) -> bool:
        """Send alert when tender document is downloaded"""
        message = f"""📄 *TENDER DOCUMENT DOWNLOADED*

📋 *Tender:* {tender_title[:60]}...
💾 *File:* {pdf_path}

🤖 Starting AI analysis of eligibility requirements...

You'll receive the eligibility report shortly.

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "normal", send_whatsapp=True)
    
    async def send_system_status_alert(self, status: str, message_text: str) -> bool:
        """Send system status alerts"""
        status_emojis = {
            "error": "❌",
            "warning": "⚠️",
            "success": "✅",
            "info": "ℹ️"
        }
        
        emoji = status_emojis.get(status, "ℹ️")
        
        message = f"""{emoji} *SYSTEM ALERT*

*Status:* {status.upper()}
*Message:* {message_text}

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "high", send_whatsapp=True)
    
    async def send_captcha_alert(self, tender_id: str, portal: str) -> bool:
        """Send CAPTCHA alert requiring human intervention"""
        message = f"""🤖 *CAPTCHA DETECTED*

*Portal:* {portal.upper()}
*Tender:* {tender_id}

⚠️ *Human intervention required*
The system has paused automation and needs you to solve a CAPTCHA.

Please check the browser window and complete the CAPTCHA to continue.

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "critical", send_whatsapp=True)
    
    async def send_bid_preparation_alert(self, tender_title: str, bid_status: str) -> bool:
        """Send bid preparation status alert"""
        message = f"""📝 *BID PREPARATION UPDATE*

📋 *Tender:* {tender_title[:60]}...
📊 *Status:* {bid_status}

{"✅ Bid draft ready for your review!" if bid_status == "Ready" else "🔄 Preparing bid documents..."}

*Next Step:* Review and approve the bid before submission.

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "high", send_whatsapp=True)
    
    async def send_search_started_alert(self, keyword: str) -> bool:
        """Send alert when search is started"""
        message = f"""🔍 *TENDER SEARCH STARTED*

*Keyword:* {keyword}
*Portal:* GeM (bidplus.gem.gov.in)

🤖 Searching for relevant tenders...
📄 Will download and analyze documents automatically.

*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        return await self.send_notification(message, "normal", send_whatsapp=True)
    
    async def test_whatsapp_connection(self) -> bool:
        """Test WhatsApp connection"""
        test_message = f"""🧪 *TEST MESSAGE*

✅ WhatsApp integration is working!

*System:* MSME Tender Automation
*Time:* {datetime.now().strftime('%d/%m/%Y %H:%M')}

You will receive notifications for:
• New tender discoveries
• Eligibility analysis results  
• Deadline alerts
• System status updates"""
        
        return await self.send_whatsapp_message(test_message)