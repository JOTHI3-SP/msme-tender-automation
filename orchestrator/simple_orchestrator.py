import asyncio
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from agents.portal_monitor_agent import PortalMonitorAgent
from agents.document_parser_agent import DocumentParserAgent
from agents.eligibility_matcher_agent import EligibilityMatcherAgent
from agents.browser_navigator_agent import BrowserNavigatorAgent
from agents.bid_preparation_agent import BidPreparationAgent
from services.notification_service import NotificationService
from database.database import TenderDatabase

class TenderAutomationOrchestrator:
    def __init__(self):
        self.logger = logging.getLogger("orchestrator")
        self.db = TenderDatabase()
        self.notification_service = NotificationService()
        
        # Initialize agents
        self.portal_monitor = PortalMonitorAgent()
        self.document_parser = DocumentParserAgent()
        self.eligibility_matcher = EligibilityMatcherAgent()
        self.browser_navigator = BrowserNavigatorAgent()
        self.bid_preparation = BidPreparationAgent()
    
    async def run_full_automation(self) -> Dict[str, Any]:
        """Run full tender automation workflow"""
        try:
            self.logger.info("Starting full tender automation workflow")
            
            results = {}
            errors = []
            
            # Step 1: Monitor portals
            self.logger.info("Step 1: Monitoring portals")
            monitor_result = await self.portal_monitor.execute({})
            results["monitor_portals"] = monitor_result
            
            if monitor_result["status"] != "success":
                errors.append(f"Portal monitoring failed: {monitor_result.get('message', 'Unknown error')}")
                return {"status": "error", "results": results, "errors": errors}
            
            # Step 2: Parse documents for discovered tenders
            discovered_tenders = monitor_result.get("tenders", [])
            if discovered_tenders:
                self.logger.info(f"Step 2: Parsing documents for {len(discovered_tenders)} tenders")
                parse_results = []
                
                for tender in discovered_tenders:
                    tender_id = tender.get("tender_id")
                    if tender_id:
                        parse_result = await self.document_parser.execute({"tender_id": tender_id})
                        parse_results.append(parse_result)
                
                results["parse_documents"] = parse_results
            
            # Step 3: Check eligibility
            self.logger.info("Step 3: Checking eligibility")
            eligibility_results = []
            
            for tender in discovered_tenders:
                tender_id = tender.get("tender_id")
                if tender_id:
                    eligibility_result = await self.eligibility_matcher.execute({"tender_id": tender_id})
                    eligibility_results.append(eligibility_result)
            
            results["check_eligibility"] = eligibility_results
            
            # Step 4: Prepare bids for eligible tenders
            self.logger.info("Step 4: Preparing bids")
            eligible_tenders = self.db.get_tenders(status="eligible")
            bid_results = []
            
            for tender_data in eligible_tenders:
                tender_id = tender_data["tender_id"]
                bid_result = await self.bid_preparation.execute({"tender_id": tender_id})
                bid_results.append(bid_result)
            
            results["prepare_bid"] = bid_results
            
            self.logger.info("Tender automation workflow completed successfully")
            
            return {
                "status": "success",
                "results": results,
                "errors": errors
            }
            
        except Exception as e:
            self.logger.error(f"Error in full automation: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def handle_user_query(self, query: str) -> Dict[str, Any]:
        """Handle user queries about tenders with intelligent analysis"""
        try:
            self.logger.info(f"Processing user query: {query}")
            
            query_lower = query.lower()
            
            # Get tender data
            all_tenders = self.db.get_tenders()
            eligible_tenders = [t for t in all_tenders if (t.get("eligibility_score") or 0) >= 70]
            
            # Handle specific tender analysis queries
            if "analyse" in query_lower or "analyze" in query_lower:
                if "pump" in query_lower:
                    return await self.analyze_pump_tenders(all_tenders)
                elif "textile" in query_lower:
                    return await self.analyze_textile_tenders(all_tenders)
                elif "all" in query_lower:
                    return await self.analyze_all_tenders(all_tenders)
                else:
                    # General analysis
                    return await self.analyze_category_tenders(query_lower, all_tenders)
            
            # Handle different types of queries
            elif "how many" in query_lower and "tender" in query_lower:
                response = f"Found {len(all_tenders)} total tenders, {len(eligible_tenders)} are eligible for bidding."
            
            elif "eligible" in query_lower:
                if not eligible_tenders:
                    response = "No eligible tenders found at the moment."
                else:
                    response = f"Found {len(eligible_tenders)} eligible tenders:\n\n"
                    for tender in eligible_tenders[:5]:  # Show first 5
                        response += f"• {tender['title'][:60]}...\n"
                        response += f"  Score: {tender.get('eligibility_score', 0)}%\n"
                        response += f"  Category: {tender['category']}\n"
                        response += f"  Deadline: {tender['deadline']}\n\n"
            
            elif "status" in query_lower:
                status_counts = {}
                for tender in all_tenders:
                    status = tender.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                response = "Tender Status Summary:\n\n"
                for status, count in status_counts.items():
                    response += f"• {status.title()}: {count}\n"
            
            elif "deadline" in query_lower:
                upcoming_deadlines = []
                for tender in all_tenders:
                    if (tender.get("eligibility_score") or 0) >= 70:
                        upcoming_deadlines.append({
                            "title": tender["title"],
                            "deadline": tender["deadline"],
                            "category": tender["category"]
                        })
                
                if not upcoming_deadlines:
                    response = "No upcoming deadlines for eligible tenders."
                else:
                    response = "Upcoming Deadlines for Eligible Tenders:\n\n"
                    for tender in sorted(upcoming_deadlines, key=lambda x: x["deadline"])[:5]:
                        response += f"• {tender['title'][:50]}...\n"
                        response += f"  Category: {tender['category']}\n"
                        response += f"  Deadline: {tender['deadline']}\n\n"
            
            elif "pump" in query_lower and ("show" in query_lower or "list" in query_lower):
                pump_tenders = [t for t in all_tenders if "pump" in t['title'].lower() or "pump" in t['category'].lower()]
                if pump_tenders:
                    response = f"Found {len(pump_tenders)} pump-related tenders:\n\n"
                    for tender in pump_tenders:
                        score = tender.get("eligibility_score", 0)
                        status = "✅ Eligible" if score >= 70 else "❌ Not Eligible"
                        response += f"• {tender['title'][:60]}...\n"
                        response += f"  {status} ({score}%)\n"
                        response += f"  Category: {tender['category']}\n\n"
                else:
                    response = "No pump-related tenders found."
            
            else:
                response = f"I can help you with tender information. Try asking about:\n• How many tenders are available?\n• Which tenders are eligible?\n• What's the status of tenders?\n• What are the upcoming deadlines?\n• Analyze pump tenders\n• Show pump tenders\n\nYour query: '{query}'"
            
            return {
                "status": "success",
                "query": query,
                "response": response
            }
            
        except Exception as e:
            self.logger.error(f"Error handling user query: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def analyze_pump_tenders(self, all_tenders: List[Dict]) -> Dict[str, Any]:
        """Analyze pump-related tenders by accessing real GeM portal and downloading PDFs"""
        try:
            self.logger.info("Starting real-time pump tender analysis from GeM portal...")
            
            # First, trigger fresh portal monitoring to get latest tenders
            monitor_result = await self.portal_monitor.execute({})
            
            if monitor_result["status"] == "success":
                # Get all tenders including newly discovered ones
                all_tenders = self.db.get_tenders()
                
                # Filter pump-related tenders
                pump_tenders = []
                for tender in all_tenders:
                    title_lower = tender['title'].lower()
                    desc_lower = tender.get('description', '').lower()
                    category_lower = tender.get('category', '').lower()
                    
                    if any(keyword in title_lower or keyword in desc_lower or keyword in category_lower 
                           for keyword in ['pump', 'pumping', 'centrifugal', 'submersible', 'motor']):
                        pump_tenders.append(tender)
                
                if not pump_tenders:
                    return {
                        "status": "success",
                        "query": "analyze pump tenders",
                        "response": "No pump-related tenders found on GeM portal at this time. The system will continue monitoring for new opportunities."
                    }
                
                # Analyze each pump tender by downloading and parsing documents
                analyzed_tenders = []
                for tender in pump_tenders[:5]:  # Analyze top 5 pump tenders
                    self.logger.info(f"Analyzing pump tender: {tender['title']}")
                    
                    # Parse documents for this tender
                    parse_result = await self.document_parser.execute({
                        "tender_id": tender["tender_id"]
                    })
                    
                    if parse_result["status"] == "success":
                        # Check eligibility
                        eligibility_result = await self.eligibility_matcher.execute({
                            "tender_id": tender["tender_id"]
                        })
                        
                        if eligibility_result["status"] == "success":
                            tender["eligibility_score"] = eligibility_result["eligibility_score"]
                            tender["eligibility_details"] = eligibility_result.get("details", [])
                            analyzed_tenders.append(tender)
                
                # Generate comprehensive analysis response
                response = f"🔧 **REAL-TIME PUMP TENDER ANALYSIS FROM GeM PORTAL**\n\n"
                response += f"**Fresh Data Summary:**\n"
                response += f"• Portal scan completed: {monitor_result.get('discovered_count', 0)} new tenders found\n"
                response += f"• Pump-related tenders identified: {len(pump_tenders)}\n"
                response += f"• Detailed analysis completed: {len(analyzed_tenders)} tenders\n\n"
                
                if analyzed_tenders:
                    eligible_pumps = [t for t in analyzed_tenders if (t.get("eligibility_score") or 0) >= 70]
                    
                    if eligible_pumps:
                        response += "**✅ ELIGIBLE PUMP TENDERS (WITH PDF ANALYSIS):**\n\n"
                        for i, tender in enumerate(eligible_pumps, 1):
                            score = tender.get("eligibility_score", 0)
                            response += f"{i}. **{tender['title'][:70]}...**\n"
                            response += f"   • Eligibility Score: {score}%\n"
                            response += f"   • Category: {tender['category']}\n"
                            response += f"   • Deadline: {tender['deadline']}\n"
                            response += f"   • Portal: {tender['portal'].upper()}\n"
                            
                            # Add analysis details from PDF parsing
                            if tender.get("eligibility_details"):
                                response += f"   • Analysis: {'; '.join(tender['eligibility_details'][:2])}\n"
                            response += "\n"
                    
                    non_eligible = [t for t in analyzed_tenders if (t.get("eligibility_score") or 0) < 70]
                    if non_eligible:
                        response += "**❌ NON-ELIGIBLE PUMP TENDERS:**\n\n"
                        for i, tender in enumerate(non_eligible[:3], 1):
                            score = tender.get("eligibility_score", 0)
                            response += f"{i}. {tender['title'][:50]}... (Score: {score}%)\n"
                
                response += f"\n**💡 ACTIONABLE RECOMMENDATIONS:**\n"
                if analyzed_tenders:
                    eligible_count = len([t for t in analyzed_tenders if (t.get("eligibility_score") or 0) >= 70])
                    if eligible_count > 0:
                        response += f"• {eligible_count} pump tenders are eligible - prepare bids immediately\n"
                        response += "• Download tender documents and review technical specifications\n"
                        response += "• Highlight your pump manufacturing experience and certifications\n"
                    else:
                        response += "• No currently eligible pump tenders found\n"
                        response += "• Review eligibility criteria and consider capability expansion\n"
                        response += "• System will continue monitoring for new opportunities\n"
                else:
                    response += "• No pump tenders available for detailed analysis\n"
                    response += "• System will monitor GeM portal continuously\n"
                
                return {
                    "status": "success",
                    "query": "analyze pump tenders",
                    "response": response
                }
            
            else:
                return {
                    "status": "error",
                    "query": "analyze pump tenders",
                    "response": f"Failed to access GeM portal: {monitor_result.get('message', 'Unknown error')}"
                }
                
        except Exception as e:
            self.logger.error(f"Error in real-time pump tender analysis: {e}")
            return {
                "status": "error",
                "query": "analyze pump tenders", 
                "response": f"Error analyzing pump tenders: {str(e)}"
            }
    
    async def analyze_textile_tenders(self, all_tenders: List[Dict]) -> Dict[str, Any]:
        """Analyze textile-related tenders specifically"""
        textile_tenders = [t for t in all_tenders if "textile" in t['title'].lower() or 
                          "textile" in t['category'].lower() or "fabric" in t['title'].lower()]
        
        if not textile_tenders:
            return {
                "status": "success",
                "query": "analyze textile tenders",
                "response": "No textile-related tenders found in the database."
            }
        
        eligible_textiles = [t for t in textile_tenders if (t.get("eligibility_score") or 0) >= 70]
        
        response = f"🧵 **TEXTILE TENDER ANALYSIS**\n\n"
        response += f"**Summary:**\n"
        response += f"• Total textile tenders: {len(textile_tenders)}\n"
        response += f"• Eligible textile tenders: {len(eligible_textiles)}\n\n"
        
        if eligible_textiles:
            response += "**✅ ELIGIBLE TEXTILE TENDERS:**\n\n"
            for i, tender in enumerate(eligible_textiles, 1):
                score = tender.get("eligibility_score", 0)
                response += f"{i}. **{tender['title'][:70]}...**\n"
                response += f"   • Eligibility Score: {score}%\n"
                response += f"   • Category: {tender['category']}\n"
                response += f"   • Deadline: {tender['deadline']}\n\n"
        
        return {
            "status": "success",
            "query": "analyze textile tenders",
            "response": response
        }
    
    async def analyze_category_tenders(self, query: str, all_tenders: List[Dict]) -> Dict[str, Any]:
        """Analyze tenders by category based on query"""
        # Extract category from query
        categories = ["industrial", "equipment", "maintenance", "agricultural", "testing", "it", "software"]
        found_category = None
        
        for category in categories:
            if category in query:
                found_category = category
                break
        
        if not found_category:
            return {
                "status": "success",
                "query": query,
                "response": "Please specify a category to analyze (e.g., pump, textile, industrial, equipment, etc.)"
            }
        
        category_tenders = [t for t in all_tenders if found_category in t['category'].lower() or 
                           found_category in t['title'].lower()]
        
        if not category_tenders:
            return {
                "status": "success",
                "query": query,
                "response": f"No {found_category}-related tenders found."
            }
        
        eligible_category = [t for t in category_tenders if (t.get("eligibility_score") or 0) >= 70]
        
        response = f"📊 **{found_category.upper()} TENDER ANALYSIS**\n\n"
        response += f"• Total {found_category} tenders: {len(category_tenders)}\n"
        response += f"• Eligible {found_category} tenders: {len(eligible_category)}\n\n"
        
        if eligible_category:
            response += f"**✅ ELIGIBLE {found_category.upper()} TENDERS:**\n\n"
            for tender in eligible_category[:5]:
                score = tender.get("eligibility_score", 0)
                response += f"• {tender['title'][:60]}... ({score}%)\n"
        
        return {
            "status": "success",
            "query": query,
            "response": response
        }