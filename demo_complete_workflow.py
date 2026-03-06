import asyncio
import logging
from datetime import datetime
from agents.portal_monitor_agent import PortalMonitorAgent
from agents.document_parser_agent import DocumentParserAgent
from agents.eligibility_matcher_agent import EligibilityMatcherAgent
from services.notification_service import NotificationService
from models.schemas import UserProfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('demo_complete_workflow.log')
    ]
)

async def test_tender_download():
    """Test the complete tender analysis workflow"""
    print("🚀 Testing Complete Tender Analysis Workflow...")
    
    # Create all agents
    portal_agent = PortalMonitorAgent()
    document_agent = DocumentParserAgent()
    eligibility_agent = EligibilityMatcherAgent()
    notification_service = NotificationService()
    
    # Create a sample user profile for testing
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
    
    print(f"👤 Using test profile: {user_profile.company_name}")
    
    # Test task
    task = {
        "search_keyword": "pump",
        "sector": "engineering"
    }
    
    print(f"🔍 Starting search for keyword: {task['search_keyword']}")
    
    try:
        # Execute the portal monitoring task
        result = await portal_agent.execute(task)
        
        print(f"\n📊 Results:")
        print(f"Status: {result['status']}")
        print(f"Total tenders found: {result.get('total_found', 0)}")
        
        if result['status'] == 'success':
            tenders = result.get('tenders', [])
            
            if tenders:
                print(f"\n✅ Successfully found {len(tenders)} tenders:")
                
                # Send initial discovery notification
                await notification_service.send_tender_discovery_alert(
                    task['search_keyword'], len(tenders), 0
                )
                
                # Process each tender for eligibility if user profile exists
                if user_profile:
                    eligible_count = 0
                    
                    for i, tender in enumerate(tenders, 1):
                        print(f"\n--- Processing Tender {i} ---")
                        print(f"ID: {tender.tender_id}")
                        print(f"Title: {tender.title}")
                        print(f"Document Path: {tender.document_path}")
                        
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
                                        
                                        print(f"Eligibility: {eligibility.status.value} ({eligibility.match_score}%)")
                                        
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
                                    
                                    else:
                                        print(f"❌ Eligibility check failed: {eligibility_result.get('error')}")
                                
                                else:
                                    print(f"❌ Document parsing failed: {parse_result.get('error')}")
                            
                            except Exception as e:
                                print(f"❌ Error processing tender {i}: {e}")
                        
                        else:
                            print("❌ No PDF downloaded")
                    
                    # Send final summary
                    await notification_service.send_notification(
                        f"🎯 Analysis Complete: {eligible_count}/{len(tenders)} tenders are eligible for your company!",
                        "high", send_whatsapp=True
                    )
                    
                    print(f"\n📊 Final Summary:")
                    print(f"Total Tenders: {len(tenders)}")
                    print(f"Eligible Tenders: {eligible_count}")
                    print(f"PDFs Downloaded: {len([t for t in tenders if t.document_path])}")
                
                else:
                    print("⚠️ No user profile found - skipping eligibility analysis")
                    for i, tender in enumerate(tenders, 1):
                        print(f"\n--- Tender {i} ---")
                        print(f"ID: {tender.tender_id}")
                        print(f"Title: {tender.title}")
                        print(f"Document Path: {tender.document_path}")
                        
                        if tender.document_path:
                            print(f"✅ PDF Downloaded: {tender.document_path}")
                        else:
                            print("❌ PDF Download Failed")
                
                # Check if any PDFs were actually downloaded
                downloaded_count = sum(1 for t in tenders if t.document_path)
                print(f"\n📄 Total PDFs Downloaded: {downloaded_count}/{len(tenders)}")
                
                if downloaded_count > 0:
                    print("🎉 SUCCESS: PDFs downloaded and analyzed!")
                else:
                    print("⚠️ WARNING: No PDFs were downloaded")
            
            else:
                print("❌ No tenders found")
        
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logging.error(f"Test error: {e}", exc_info=True)

if __name__ == "__main__":
    print("🔧 Testing Updated Portal Monitor Agent...")
    asyncio.run(test_tender_download())
    print("\n✅ Test completed! Check the logs and screenshots for details.")