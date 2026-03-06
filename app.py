import chainlit as cl
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

# Import our agents and models
from agents.portal_monitor_agent import PortalMonitorAgent
from agents.document_parser_agent import DocumentParserAgent
from agents.eligibility_matcher_agent import EligibilityMatcherAgent
from models.schemas import UserProfile, Tender, EligibilityResult
from services.notification_service import NotificationService
from database.database import TenderDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tender_automation.log'),
        logging.StreamHandler()
    ]
)

# Initialize components
portal_agent = PortalMonitorAgent()
document_agent = DocumentParserAgent()
eligibility_agent = EligibilityMatcherAgent()
notification_service = NotificationService()
db = TenderDatabase()

# Global user profile (in real app, this would be per-user)
user_profile = None

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    await cl.Message(
        content="""
# 🚀 MSME Tender Automation System

Welcome! I'm your AI assistant for **complete automated government tender analysis**.

## 🤖 **What I do automatically:**
- 🔍 **Search GeM Portal** for tenders based on your keywords
- 📄 **Download & Analyze** ALL tender PDFs using Groq AI
- ✅ **Check Eligibility** with proper MSME/Startup relaxation logic
- 📱 **Send WhatsApp Notifications** for each step
- 📊 **Provide Complete Reports** with detailed analysis
- ⏰ **Track Deadlines** and send urgent alerts

## 🎯 **Complete Automated Workflow:**
Just type: `search [keyword] tenders` and I will:
1. Find all matching tenders on GeM portal
2. Download every PDF document
3. Analyze requirements using AI
4. Check your company's eligibility 
5. Send WhatsApp updates for each tender
6. Provide final summary with eligible tenders

## 📱 **Quick Commands:**
- `search pump tenders` - **Complete automated analysis for pump tenders**
- `search textile tenders` - **Full workflow for textile tenders**
- `search engineering tenders` - **End-to-end analysis for engineering**
- `setup profile` - Configure your company profile (optional - uses smart defaults)
- `show deadlines` - View upcoming deadlines
- `help` - Show all available commands

**🎉 Ready to automate your tender discovery and analysis!**
**Just search for any keyword and watch the magic happen!**
        """,
        author="System"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle user messages"""
    user_input = message.content.lower().strip()
    
    try:
        # Route to appropriate handler
        if user_input.startswith("search"):
            await handle_search_tenders(message.content)
        elif user_input.startswith("setup profile"):
            await handle_profile_setup()
        elif user_input.startswith("check eligibility"):
            await handle_eligibility_check(message.content)
        elif user_input.startswith("show deadlines"):
            await handle_deadline_query()
        elif user_input.startswith("analyze tender"):
            await handle_tender_analysis(message.content)
        elif user_input == "help":
            await handle_help()
        else:
            await handle_general_query(message.content)
            
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        await cl.Message(
            content=f"❌ Error processing your request: {str(e)}",
            author="System"
        ).send()

async def handle_search_tenders(user_input: str):
    """Handle tender search requests with complete automated workflow"""
    try:
        # Extract search keyword
        parts = user_input.split()
        keyword = "pump"  # default
        if len(parts) > 1:
            keyword = " ".join(parts[1:]).replace("tenders", "").strip()
        
        await cl.Message(
            content=f"🔍 Searching GeM portal for '{keyword}' tenders and starting complete analysis...",
            author="System"
        ).send()
        
        # Create default user profile if not exists
        global user_profile
        if not user_profile:
            user_profile = UserProfile(
                company_name="ABC Engineering Pvt Ltd",
                annual_turnover=75.0,  # 75 lakhs
                experience_years=5,
                location="Coimbatore, Tamil Nadu",
                state="Tamil Nadu",
                business_sectors=["pump manufacturing", "engineering"],
                iso_certifications=["ISO 9001:2015"],
                other_certifications=[],
                contact_number="+91-9876543210",
                email="info@abcengineering.com",
                pan_number="ABCDE1234F",
                gst_number="33ABCDE1234F1Z5",
                is_msme=True,  # Company is MSME
                is_startup=False,
                can_pay_emd=True,
                max_emd_amount=10.0  # Can provide up to 10 lakhs EMD
            )
            
            await cl.Message(
                content=f"👤 Using default profile: {user_profile.company_name} (MSME Company)",
                author="System"
            ).send()
        
        # Search for tenders
        task = {
            "search_keyword": keyword,
            "sector": "engineering"
        }
        
        result = await portal_agent.execute(task)
        
        if result["status"] == "success":
            tenders = result["tenders"]
            
            if not tenders:
                await cl.Message(
                    content=f"No tenders found for keyword '{keyword}'. Try different keywords like 'pump', 'textile', 'engineering', etc.",
                    author="System"
                ).send()
                return
            
            await cl.Message(
                content=f"## 🎯 Found {len(tenders)} tenders for '{keyword}'\n\n🤖 **Starting Complete Automated Analysis...**\n- Downloading PDFs\n- Analyzing requirements\n- Checking eligibility\n- Sending WhatsApp notifications",
                author="System"
            ).send()
            
            # Store tenders in session for later reference
            cl.user_session.set("last_search_results", tenders)
            
            # Send initial discovery notification
            await notification_service.send_tender_discovery_alert(
                keyword, len(tenders), 0
            )
            
            # Process each tender automatically (complete workflow from demo)
            eligible_count = 0
            processed_count = 0
            
            for i, tender in enumerate(tenders, 1):
                await cl.Message(
                    content=f"📄 **Processing Tender {i}/{len(tenders)}**\n**ID:** {tender.tender_id}\n**Title:** {tender.title[:60]}...",
                    author="System"
                ).send()
                
                if tender.document_path:
                    try:
                        # Parse document
                        parse_task = {
                            "tender": tender,
                            "document_path": tender.document_path
                        }
                        
                        parse_result = await document_agent.execute(parse_task)
                        
                        if parse_result["status"] == "success":
                            requirements = parse_result["requirements"]
                            
                            # Check eligibility
                            eligibility_task = {
                                "tender": tender,
                                "user_profile": user_profile,
                                "requirements": requirements
                            }
                            
                            eligibility_result = await eligibility_agent.execute(eligibility_task)
                            
                            if eligibility_result["status"] == "success":
                                eligibility = eligibility_result["eligibility_result"]
                                tender.eligibility_result = eligibility
                                
                                status_emoji = "✅" if eligibility.status.value == "Eligible" else "❌" if eligibility.status.value == "Not Eligible" else "⚠️"
                                
                                await cl.Message(
                                    content=f"{status_emoji} **Eligibility:** {eligibility.status.value} ({eligibility.match_score}%)",
                                    author="System"
                                ).send()
                                
                                if eligibility.status.value == "Eligible":
                                    eligible_count += 1
                                
                                # Send individual WhatsApp notification
                                await notification_service.send_eligibility_notification(
                                    tender.title, eligibility.status.value, eligibility.match_score, eligibility.reasons
                                )
                                
                                # Send deadline alert if urgent
                                days_remaining = (tender.deadline - datetime.now()).days
                                if days_remaining <= 7 and eligibility.status.value == "Eligible":
                                    hours_remaining = max(1, days_remaining * 24)
                                    await notification_service.send_deadline_alert(
                                        tender.title, tender.deadline.strftime('%d/%m/%Y %H:%M'), hours_remaining
                                    )
                                
                                processed_count += 1
                            
                            else:
                                await cl.Message(
                                    content=f"❌ Eligibility check failed: {eligibility_result.get('error')}",
                                    author="System"
                                ).send()
                        
                        else:
                            await cl.Message(
                                content=f"❌ Document parsing failed: {parse_result.get('error')}",
                                author="System"
                            ).send()
                    
                    except Exception as e:
                        await cl.Message(
                            content=f"❌ Error processing tender {i}: {e}",
                            author="System"
                        ).send()
                        logging.error(f"Error processing tender {i}: {e}")
                
                else:
                    await cl.Message(
                        content="❌ No PDF downloaded",
                        author="System"
                    ).send()
            
            # Send final summary
            await notification_service.send_notification(
                f"🎯 Analysis Complete: {eligible_count}/{len(tenders)} tenders are eligible for your company!",
                "high", send_whatsapp=True
            )
            
            # Display final results
            downloaded_count = sum(1 for t in tenders if t.document_path)
            
            final_content = f"""
## 🎉 **Complete Analysis Finished!**

### 📊 **Final Results:**
- **Total Tenders Found:** {len(tenders)}
- **PDFs Downloaded:** {downloaded_count}
- **Tenders Analyzed:** {processed_count}
- **Eligible Tenders:** {eligible_count}

### ✅ **Eligible Tenders:**
"""
            
            for i, tender in enumerate(tenders, 1):
                if hasattr(tender, 'eligibility_result') and tender.eligibility_result and tender.eligibility_result.status.value == "Eligible":
                    days_remaining = (tender.deadline - datetime.now()).days
                    urgency = "🚨" if days_remaining <= 7 else "⏰" if days_remaining <= 30 else "📅"
                    
                    final_content += f"""
**{i}. {tender.title[:60]}...**
- Score: {tender.eligibility_result.match_score}%
- Deadline: {urgency} {tender.deadline.strftime('%d/%m/%Y')} ({days_remaining} days)
- Portal: {tender.portal.upper()}
"""
            
            final_content += f"""
### 📱 **WhatsApp Notifications Sent:**
- Tender discovery alert
- Individual eligibility results for each tender
- Deadline alerts for urgent tenders
- Final summary notification

**All analysis complete! Check your WhatsApp for detailed notifications.**
            """
            
            await cl.Message(content=final_content, author="System").send()
            
        else:
            await cl.Message(
                content=f"❌ Error searching tenders: {result.get('error', 'Unknown error')}",
                author="System"
            ).send()
            
    except Exception as e:
        logging.error(f"Error in handle_search_tenders: {e}")
        await cl.Message(
            content=f"❌ Error searching tenders: {str(e)}",
            author="System"
        ).send()

async def handle_eligibility_check(user_input: str):
    """Handle eligibility checking"""
    try:
        global user_profile
        
        if not user_profile:
            await cl.Message(
                content="⚠️ Please setup your company profile first using `setup profile`",
                author="System"
            ).send()
            return
        
        # Get tender from last search or URL
        tender = None
        tenders = cl.user_session.get("last_search_results", [])
        
        # Extract tender number or URL
        parts = user_input.split()
        if len(parts) > 2:
            try:
                tender_num = int(parts[2]) - 1  # Convert to 0-based index
                if 0 <= tender_num < len(tenders):
                    tender = tenders[tender_num]
            except ValueError:
                # Might be a URL
                tender_url = parts[2]
                await cl.Message(
                    content=f"🔍 Analyzing tender from URL: {tender_url}",
                    author="System"
                ).send()
                tender = await portal_agent.get_tender_by_url(tender_url)
        
        if not tender:
            await cl.Message(
                content="❌ Please specify a tender number from the last search or provide a tender URL",
                author="System"
            ).send()
            return
        
        await cl.Message(
            content=f"📄 Analyzing tender: {tender.title[:60]}...",
            author="System"
        ).send()
        
        # Download and parse document
        if tender.documents_url:
            document_path = await portal_agent.download_tender_document(tender)
            
            if document_path:
                # Parse document
                parse_task = {
                    "tender": tender,
                    "document_path": document_path
                }
                
                parse_result = await document_agent.execute(parse_task)
                
                if parse_result["status"] == "success":
                    requirements = parse_result["requirements"]
                    
                    # Check eligibility
                    eligibility_task = {
                        "tender": tender,
                        "user_profile": user_profile,
                        "requirements": requirements
                    }
                    
                    eligibility_result = await eligibility_agent.execute(eligibility_task)
                    
                    if eligibility_result["status"] == "success":
                        eligibility = eligibility_result["eligibility_result"]
                        
                        # Create detailed report
                        status_emoji = "✅" if eligibility.status.value == "Eligible" else "❌" if eligibility.status.value == "Not Eligible" else "⚠️"
                        
                        content = f"""
## {status_emoji} Eligibility Analysis Report

**Tender:** {tender.title}  
**Status:** {eligibility.status.value}  
**Match Score:** {eligibility.match_score}%  
**Deadline:** {tender.deadline.strftime('%d/%m/%Y %H:%M')}

### 📋 Analysis Results:
"""
                        
                        for reason in eligibility.reasons:
                            content += f"- {reason}\n"
                        
                        if eligibility.missing_criteria:
                            content += f"\n### ❌ Missing Requirements:\n"
                            for criteria in eligibility.missing_criteria:
                                content += f"- {criteria}\n"
                        
                        if eligibility.recommendations:
                            content += f"\n### 💡 Recommendations:\n"
                            for rec in eligibility.recommendations:
                                content += f"- {rec}\n"
                        
                        if eligibility.status.value == "Eligible":
                            content += f"\n### 🎯 Next Steps:\n- Review the complete tender document\n- Prepare your bid proposal\n- Submit before deadline: {tender.deadline.strftime('%d/%m/%Y %H:%M')}"
                        
                        # Send WhatsApp notification about document download
                        if document_path:
                            await notification_service.send_document_download_alert(
                                tender.title, document_path
                            )
                        
                        # Parse document
                        parse_task = {
                            "tender": tender,
                            "document_path": document_path
                        }
                        
                        parse_result = await document_agent.execute(parse_task)
                        
                        if parse_result["status"] == "success":
                            requirements = parse_result["requirements"]
                            
                            # Check eligibility
                            eligibility_task = {
                                "tender": tender,
                                "user_profile": user_profile,
                                "requirements": requirements
                            }
                            
                            eligibility_result = await eligibility_agent.execute(eligibility_task)
                            
                            if eligibility_result["status"] == "success":
                                eligibility = eligibility_result["eligibility_result"]
                                
                                # Create detailed report
                                status_emoji = "✅" if eligibility.status.value == "Eligible" else "❌" if eligibility.status.value == "Not Eligible" else "⚠️"
                                
                                content = f"""
## {status_emoji} Eligibility Analysis Report

**Tender:** {tender.title}  
**Status:** {eligibility.status.value}  
**Match Score:** {eligibility.match_score}%  
**Deadline:** {tender.deadline.strftime('%d/%m/%Y %H:%M')}

### 📋 Analysis Results:
"""
                                
                                for reason in eligibility.reasons:
                                    content += f"- {reason}\n"
                                
                                if eligibility.missing_criteria:
                                    content += f"\n### ❌ Missing Requirements:\n"
                                    for criteria in eligibility.missing_criteria:
                                        content += f"- {criteria}\n"
                                
                                if eligibility.recommendations:
                                    content += f"\n### 💡 Recommendations:\n"
                                    for rec in eligibility.recommendations:
                                        content += f"- {rec}\n"
                                
                                if eligibility.status.value == "Eligible":
                                    content += f"\n### 🎯 Next Steps:\n- Review the complete tender document\n- Prepare your bid proposal\n- Submit before deadline: {tender.deadline.strftime('%d/%m/%Y %H:%M')}"
                                
                                await cl.Message(content=content, author="System").send()
                                
                                # Send WhatsApp notification
                                await notification_service.send_eligibility_notification(
                                    tender.title, eligibility.status.value, eligibility.match_score, eligibility.reasons
                                )
                                
                                # Send deadline alert if urgent
                                days_remaining = (tender.deadline - datetime.now()).days
                                if days_remaining <= 7:
                                    hours_remaining = max(1, days_remaining * 24)
                                    await notification_service.send_deadline_alert(
                                        tender.title, tender.deadline.strftime('%d/%m/%Y %H:%M'), hours_remaining
                                    )
                            
                            else:
                                await cl.Message(
                                    content=f"❌ Error checking eligibility: {eligibility_result.get('error')}",
                                    author="System"
                                ).send()
                        else:
                            await cl.Message(
                                content=f"❌ Error parsing document: {parse_result.get('error')}",
                                author="System"
                            ).send()
                        
                    else:
                        await cl.Message(
                            content=f"❌ Error checking eligibility: {eligibility_result.get('error')}",
                            author="System"
                        ).send()
                else:
                    await cl.Message(
                        content=f"❌ Error parsing document: {parse_result.get('error')}",
                        author="System"
                    ).send()
            else:
                await cl.Message(
                    content="❌ Could not download tender document",
                    author="System"
                ).send()
        else:
            await cl.Message(
                content="❌ No document URL found for this tender",
                author="System"
            ).send()
            
    except Exception as e:
        logging.error(f"Error in handle_eligibility_check: {e}")
        await cl.Message(
            content=f"❌ Error checking eligibility: {str(e)}",
            author="System"
        ).send()

async def handle_profile_setup():
    """Handle company profile setup"""
    try:
        global user_profile
        
        await cl.Message(
            content="""
## 🏢 Company Profile Setup

Please provide your company details. You can either:

1. **Provide all details at once:**
```
Company: ABC Engineering Pvt Ltd
Turnover: 75 lakhs
Experience: 5 years
Location: Coimbatore, Tamil Nadu
State: Tamil Nadu
Sectors: pump manufacturing, textile machinery
Certifications: ISO 9001:2015, ISO 14001:2015
Contact: +91-9876543210
Email: info@abcengineering.com
PAN: ABCDE1234F
GST: 33ABCDE1234F1Z5
```

2. **Or I'll ask you step by step**

Just type your details or say "step by step" for guided setup.
            """,
            author="System"
        ).send()
        
        # Wait for user response
        response = await cl.AskUserMessage(
            content="Please provide your company details:",
            timeout=300
        ).send()
        
        if response:
            if "step by step" in response.content.lower():
                await handle_guided_profile_setup()
            else:
                await parse_profile_from_text(response.content)
        
    except Exception as e:
        logging.error(f"Error in handle_profile_setup: {e}")
        await cl.Message(
            content=f"❌ Error setting up profile: {str(e)}",
            author="System"
        ).send()

async def parse_profile_from_text(text: str):
    """Parse company profile from user text"""
    try:
        global user_profile
        
        lines = text.strip().split('\n')
        profile_data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'company' in key or 'name' in key:
                    profile_data['company_name'] = value
                elif 'turnover' in key:
                    # Extract number from turnover
                    import re
                    numbers = re.findall(r'\d+(?:\.\d+)?', value)
                    if numbers:
                        profile_data['annual_turnover'] = float(numbers[0])
                elif 'experience' in key:
                    numbers = re.findall(r'\d+', value)
                    if numbers:
                        profile_data['experience_years'] = int(numbers[0])
                elif 'location' in key:
                    profile_data['location'] = value
                elif 'state' in key:
                    profile_data['state'] = value
                elif 'sector' in key:
                    profile_data['business_sectors'] = [s.strip() for s in value.split(',')]
                elif 'certification' in key:
                    profile_data['iso_certifications'] = [s.strip() for s in value.split(',')]
                elif 'contact' in key or 'phone' in key:
                    profile_data['contact_number'] = value
                elif 'email' in key:
                    profile_data['email'] = value
                elif 'pan' in key:
                    profile_data['pan_number'] = value
                elif 'gst' in key:
                    profile_data['gst_number'] = value
        
        # Create user profile with defaults
        user_profile = UserProfile(
            company_name=profile_data.get('company_name', 'Your Company'),
            annual_turnover=profile_data.get('annual_turnover', 50.0),
            experience_years=profile_data.get('experience_years', 5),
            location=profile_data.get('location', 'Coimbatore, Tamil Nadu'),
            state=profile_data.get('state', 'Tamil Nadu'),
            business_sectors=profile_data.get('business_sectors', ['engineering']),
            iso_certifications=profile_data.get('iso_certifications', []),
            other_certifications=[],
            contact_number=profile_data.get('contact_number', '+91-9876543210'),
            email=profile_data.get('email', 'info@company.com'),
            pan_number=profile_data.get('pan_number', 'ABCDE1234F'),
            gst_number=profile_data.get('gst_number', '33ABCDE1234F1Z5')
        )
        
        await cl.Message(
            content=f"""
## ✅ Profile Setup Complete!

**Company:** {user_profile.company_name}  
**Annual Turnover:** ₹{user_profile.annual_turnover} lakhs  
**Experience:** {user_profile.experience_years} years  
**Location:** {user_profile.location}  
**Sectors:** {', '.join(user_profile.business_sectors)}  
**Certifications:** {', '.join(user_profile.iso_certifications) if user_profile.iso_certifications else 'None'}

You can now search for tenders and check eligibility!
            """,
            author="System"
        ).send()
        
    except Exception as e:
        logging.error(f"Error parsing profile: {e}")
        await cl.Message(
            content=f"❌ Error parsing profile. Please try again with the correct format.",
            author="System"
        ).send()

async def handle_deadline_query():
    """Handle deadline queries"""
    try:
        tenders = cl.user_session.get("last_search_results", [])
        
        if not tenders:
            await cl.Message(
                content="No tenders found. Please search for tenders first using `search [keyword]`",
                author="System"
            ).send()
            return
        
        # Sort by deadline
        tenders.sort(key=lambda t: t.deadline)
        
        content = "## ⏰ Upcoming Tender Deadlines\n\n"
        
        for i, tender in enumerate(tenders[:10], 1):
            days_remaining = (tender.deadline - datetime.now()).days
            
            if days_remaining < 0:
                urgency = "🔴 EXPIRED"
            elif days_remaining <= 3:
                urgency = "🚨 URGENT"
            elif days_remaining <= 7:
                urgency = "⚠️ SOON"
            else:
                urgency = "📅 UPCOMING"
            
            content += f"""
### {i}. {tender.title[:60]}...
**Deadline:** {urgency} {tender.deadline.strftime('%d/%m/%Y %H:%M')}  
**Days Remaining:** {days_remaining}  
**Portal:** {tender.portal.upper()}

---
"""
        
        await cl.Message(content=content, author="System").send()
        
    except Exception as e:
        logging.error(f"Error in handle_deadline_query: {e}")
        await cl.Message(
            content=f"❌ Error retrieving deadlines: {str(e)}",
            author="System"
        ).send()

async def handle_help():
    """Show help information"""
    content = """
## 🆘 Help - Available Commands

### 🔍 Search & Discovery
- `search pump tenders` - Search for pump-related tenders
- `search textile machinery` - Search for textile tenders
- `search [keyword] tenders` - Search for any keyword

### ✅ Eligibility Analysis
- `check eligibility 1` - Check eligibility for tender #1 from last search
- `check eligibility [tender_url]` - Analyze specific tender URL
- `analyze tender 1` - Detailed analysis of tender #1

### 🏢 Profile Management
- `setup profile` - Configure your company profile
- `show profile` - Display current profile

### ⏰ Deadline Tracking
- `show deadlines` - View upcoming tender deadlines
- `urgent deadlines` - Show only urgent deadlines

### 💬 General Queries
- `help` - Show this help message
- Ask any question about tenders, eligibility, or the system

### 📋 Example Workflow:
1. `setup profile` - Configure your company details
2. `search pump tenders` - Find relevant tenders
3. `check eligibility 1` - Analyze first tender
4. `show deadlines` - Track important dates

**Need more help? Just ask me anything!**
    """
    
    await cl.Message(content=content, author="System").send()

async def handle_general_query(query: str):
    """Handle general queries about tenders with comprehensive analysis"""
    try:
        # Simple keyword-based responses with tender data
        query_lower = query.lower()
        
        # Get recent tenders from session or database
        tenders = cl.user_session.get("last_search_results", [])
        
        if 'how many' in query_lower and 'tender' in query_lower:
            total_tenders = len(tenders)
            eligible_tenders = len([t for t in tenders if hasattr(t, 'eligibility_result') and t.eligibility_result and t.eligibility_result.status.value == "Eligible"])
            
            response = f"""
## 📊 Tender Statistics

**Total Tenders Found:** {total_tenders}
**Eligible Tenders:** {eligible_tenders}
**Downloaded PDFs:** {len([t for t in tenders if t.document_path])}

**Recent Searches:** Available for analysis and eligibility checking.
            """
            
            await cl.Message(content=response, author="System").send()
            
            # Send WhatsApp summary
            await notification_service.send_notification(
                f"📊 Tender Summary: {total_tenders} total, {eligible_tenders} eligible tenders found",
                "normal", send_whatsapp=True
            )
        
        elif 'deadline' in query_lower:
            if tenders:
                upcoming_deadlines = []
                for tender in tenders:
                    days_remaining = (tender.deadline - datetime.now()).days
                    if days_remaining > 0:
                        upcoming_deadlines.append((tender, days_remaining))
                
                upcoming_deadlines.sort(key=lambda x: x[1])  # Sort by days remaining
                
                response = "## ⏰ Upcoming Tender Deadlines\n\n"
                
                for tender, days in upcoming_deadlines[:5]:  # Show first 5
                    urgency = "🚨" if days <= 3 else "⚠️" if days <= 7 else "📅"
                    response += f"{urgency} **{tender.tender_id}**\n"
                    response += f"Deadline: {tender.deadline.strftime('%d/%m/%Y')}\n"
                    response += f"Days remaining: {days}\n\n"
                
                await cl.Message(content=response, author="System").send()
                
                # Send WhatsApp deadline alert for urgent ones
                urgent_tenders = [t for t, d in upcoming_deadlines if d <= 7]
                if urgent_tenders:
                    await notification_service.send_notification(
                        f"🚨 {len(urgent_tenders)} tenders have deadlines within 7 days!",
                        "critical", send_whatsapp=True
                    )
            else:
                await cl.Message(content="No tenders found. Please search for tenders first.", author="System").send()
        
        elif 'eligible' in query_lower:
            if tenders:
                eligible_tenders = []
                for tender in tenders:
                    if hasattr(tender, 'eligibility_result') and tender.eligibility_result:
                        if tender.eligibility_result.status.value == "Eligible":
                            eligible_tenders.append(tender)
                
                if eligible_tenders:
                    response = f"## ✅ Eligible Tenders ({len(eligible_tenders)} found)\n\n"
                    
                    for tender in eligible_tenders:
                        response += f"**{tender.tender_id}**\n"
                        response += f"Score: {tender.eligibility_result.match_score}%\n"
                        response += f"Deadline: {tender.deadline.strftime('%d/%m/%Y')}\n\n"
                    
                    await cl.Message(content=response, author="System").send()
                    
                    # Send WhatsApp notification
                    await notification_service.send_notification(
                        f"✅ You have {len(eligible_tenders)} eligible tenders to review!",
                        "high", send_whatsapp=True
                    )
                else:
                    await cl.Message(content="No eligible tenders found. Try different search keywords or update your company profile.", author="System").send()
            else:
                await cl.Message(content="No tenders analyzed yet. Please search and analyze tenders first.", author="System").send()
        
        elif any(word in query_lower for word in ['requirements', 'criteria', 'qualification']):
            if tenders:
                response = "## 📋 Tender Requirements Summary\n\n"
                
                for tender in tenders[:3]:  # Show first 3
                    if hasattr(tender, 'requirements') and tender.requirements:
                        req = tender.requirements
                        response += f"**{tender.tender_id}**\n"
                        
                        if req.min_turnover:
                            response += f"• Min Turnover: ₹{req.min_turnover} lakhs\n"
                        if req.min_experience:
                            response += f"• Min Experience: {req.min_experience} years\n"
                        if req.required_certifications:
                            response += f"• Certifications: {', '.join(req.required_certifications)}\n"
                        if req.required_location:
                            response += f"• Location: {req.required_location}\n"
                        
                        response += "\n"
                
                await cl.Message(content=response, author="System").send()
            else:
                await cl.Message(content="No tender requirements available. Please search and analyze tenders first.", author="System").send()
        
        elif any(word in query_lower for word in ['download', 'pdf', 'document']):
            downloaded_count = len([t for t in tenders if t.document_path])
            
            response = f"""
## 📄 Document Download Status

**Total PDFs Downloaded:** {downloaded_count}
**Available for Analysis:** {downloaded_count} documents

**Recent Downloads:**
"""
            
            for tender in tenders:
                if tender.document_path:
                    response += f"• {tender.tender_id}: {tender.document_path}\n"
            
            await cl.Message(content=response, author="System").send()
        
        else:
            # General help response
            await cl.Message(
                content=f"""
I understand you're asking about: "{query}"

**Available Commands:**
• `search [keyword] tenders` - Search and download tender PDFs
• `check eligibility [number]` - Analyze specific tender eligibility
• `show deadlines` - View upcoming deadlines
• `setup profile` - Configure your company profile

**Query Examples:**
• "How many tenders are available?"
• "Which tenders have upcoming deadlines?"
• "Show me eligible tenders"
• "What are the requirements for tender 1?"

**Current Status:**
• Tenders in memory: {len(tenders)}
• PDFs downloaded: {len([t for t in tenders if t.document_path])}

Try one of these commands or ask me something specific about tenders!
                """,
                author="System"
            ).send()
            
    except Exception as e:
        logging.error(f"Error in handle_general_query: {e}")
        await cl.Message(
            content=f"❌ Error processing query: {str(e)}",
            author="System"
        ).send()

if __name__ == "__main__":
    # Run with: chainlit run app.py
    pass