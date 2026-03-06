import asyncio
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain_core.messages import HumanMessage, AIMessage
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
        
        # Build workflow graph
        self.workflow = self.build_workflow()
    
    def build_workflow(self) -> StateGraph:
        """Build LangGraph workflow for tender automation"""
        
        # Define workflow state
        class WorkflowState:
            def __init__(self):
                self.current_step = "start"
                self.tender_id = None
                self.user_query = None
                self.results = {}
                self.errors = []
                self.human_intervention_required = False
        
        # Create state graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("monitor_portals", self.monitor_portals_node)
        workflow.add_node("parse_documents", self.parse_documents_node)
        workflow.add_node("check_eligibility", self.check_eligibility_node)
        workflow.add_node("prepare_bid", self.prepare_bid_node)
        workflow.add_node("handle_user_query", self.handle_user_query_node)
        workflow.add_node("human_intervention", self.human_intervention_node)
        
        # Define edges
        workflow.add_edge("monitor_portals", "parse_documents")
        workflow.add_edge("parse_documents", "check_eligibility")
        workflow.add_edge("check_eligibility", "prepare_bid")
        workflow.add_edge("prepare_bid", END)
        workflow.add_edge("handle_user_query", END)
        workflow.add_edge("human_intervention", END)
        
        # Set entry point
        workflow.set_entry_point("monitor_portals")
        
        return workflow.compile()
    
    async def monitor_portals_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor portals for new tenders"""
        try:
            self.logger.info("Starting portal monitoring")
            
            result = await self.portal_monitor.execute({})
            
            if result["status"] == "success":
                discovered_tenders = result.get("tenders", [])
                
                if discovered_tenders:
                    # Send notification about discovered tenders
                    from models.schemas import Tender
                    tender_objects = [Tender(**t) for t in discovered_tenders]
                    await self.notification_service.send_tender_discovery_alert(tender_objects)
                
                state["results"]["monitor_portals"] = result
                state["discovered_tenders"] = discovered_tenders
            else:
                state["errors"].append(f"Portal monitoring failed: {result.get('message', 'Unknown error')}")
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error in monitor_portals_node: {e}")
            state["errors"].append(f"Portal monitoring error: {str(e)}")
            return state
    
    async def parse_documents_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Parse documents for discovered tenders"""
        try:
            discovered_tenders = state.get("discovered_tenders", [])
            
            if not discovered_tenders:
                self.logger.info("No tenders to parse")
                return state
            
            parsed_results = []
            
            for tender in discovered_tenders:
                tender_id = tender.get("tender_id")
                if tender_id:
                    self.logger.info(f"Parsing documents for tender: {tender_id}")
                    
                    result = await self.document_parser.execute({"tender_id": tender_id})
                    parsed_results.append(result)
            
            state["results"]["parse_documents"] = parsed_results
            return state
            
        except Exception as e:
            self.logger.error(f"Error in parse_documents_node: {e}")
            state["errors"].append(f"Document parsing error: {str(e)}")
            return state
    
    async def check_eligibility_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Check eligibility for parsed tenders"""
        try:
            discovered_tenders = state.get("discovered_tenders", [])
            
            if not discovered_tenders:
                return state
            
            eligibility_results = []
            
            for tender in discovered_tenders:
                tender_id = tender.get("tender_id")
                if tender_id:
                    self.logger.info(f"Checking eligibility for tender: {tender_id}")
                    
                    result = await self.eligibility_matcher.execute({"tender_id": tender_id})
                    eligibility_results.append(result)
                    
                    # Send eligibility notification
                    if result["status"] == "success":
                        tender_obj = Tender(**tender)
                        await self.notification_service.send_eligibility_alert(
                            tender_obj,
                            result["eligibility_score"],
                            result["details"]
                        )
            
            state["results"]["check_eligibility"] = eligibility_results
            return state
            
        except Exception as e:
            self.logger.error(f"Error in check_eligibility_node: {e}")
            state["errors"].append(f"Eligibility checking error: {str(e)}")
            return state
    
    async def prepare_bid_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare bids for eligible tenders"""
        try:
            # Get eligible tenders from database
            eligible_tenders = self.db.get_tenders(status="eligible")
            
            if not eligible_tenders:
                self.logger.info("No eligible tenders found")
                return state
            
            bid_results = []
            
            for tender_data in eligible_tenders:
                tender_id = tender_data["tender_id"]
                self.logger.info(f"Preparing bid for tender: {tender_id}")
                
                result = await self.bid_preparation.execute({"tender_id": tender_id})
                bid_results.append(result)
            
            state["results"]["prepare_bid"] = bid_results
            return state
            
        except Exception as e:
            self.logger.error(f"Error in prepare_bid_node: {e}")
            state["errors"].append(f"Bid preparation error: {str(e)}")
            return state
    
    async def handle_user_query_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user queries about tenders"""
        try:
            user_query = state.get("user_query", "")
            
            if not user_query:
                return state
            
            self.logger.info(f"Handling user query: {user_query}")
            
            # Process query and generate response
            response = await self.process_user_query(user_query)
            
            state["results"]["user_query"] = {
                "query": user_query,
                "response": response
            }
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error in handle_user_query_node: {e}")
            state["errors"].append(f"Query handling error: {str(e)}")
            return state
    
    async def human_intervention_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle human intervention requirements"""
        try:
            self.logger.info("Human intervention required")
            
            # Send notification about required intervention
            await self.notification_service.send_system_status_alert(
                "warning",
                "Human intervention required for CAPTCHA or bid approval"
            )
            
            state["results"]["human_intervention"] = {
                "status": "waiting",
                "message": "Human intervention required"
            }
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error in human_intervention_node: {e}")
            state["errors"].append(f"Human intervention error: {str(e)}")
            return state
    
    async def process_user_query(self, query: str) -> str:
        """Process user query and return response"""
        try:
            query_lower = query.lower()
            
            # Get tender data
            all_tenders = self.db.get_tenders()
            eligible_tenders = [t for t in all_tenders if t.get("eligibility_score", 0) >= 70]
            
            # Handle different types of queries
            if "how many" in query_lower and "tender" in query_lower:
                return f"Found {len(all_tenders)} total tenders, {len(eligible_tenders)} are eligible for bidding."
            
            elif "eligible" in query_lower:
                if not eligible_tenders:
                    return "No eligible tenders found at the moment."
                
                response = f"Found {len(eligible_tenders)} eligible tenders:\n\n"
                for tender in eligible_tenders[:5]:  # Show first 5
                    response += f"• {tender['title'][:60]}...\n"
                    response += f"  Score: {tender.get('eligibility_score', 0)}%\n"
                    response += f"  Deadline: {tender['deadline']}\n\n"
                
                return response
            
            elif "status" in query_lower:
                status_counts = {}
                for tender in all_tenders:
                    status = tender.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                response = "Tender Status Summary:\n\n"
                for status, count in status_counts.items():
                    response += f"• {status.title()}: {count}\n"
                
                return response
            
            elif "deadline" in query_lower:
                upcoming_deadlines = []
                for tender in all_tenders:
                    if tender.get("eligibility_score", 0) >= 70:
                        upcoming_deadlines.append({
                            "title": tender["title"],
                            "deadline": tender["deadline"]
                        })
                
                if not upcoming_deadlines:
                    return "No upcoming deadlines for eligible tenders."
                
                response = "Upcoming Deadlines for Eligible Tenders:\n\n"
                for tender in sorted(upcoming_deadlines, key=lambda x: x["deadline"])[:5]:
                    response += f"• {tender['title'][:50]}...\n"
                    response += f"  Deadline: {tender['deadline']}\n\n"
                
                return response
            
            else:
                return f"I can help you with tender information. Try asking about:\n• How many tenders are available?\n• Which tenders are eligible?\n• What's the status of tenders?\n• What are the upcoming deadlines?\n\nYour query: '{query}'"
        
        except Exception as e:
            return f"Sorry, I encountered an error processing your query: {str(e)}"
    
    async def run_full_automation(self) -> Dict[str, Any]:
        """Run full tender automation workflow"""
        try:
            self.logger.info("Starting full tender automation workflow")
            
            # Initialize state
            initial_state = {
                "current_step": "start",
                "results": {},
                "errors": [],
                "human_intervention_required": False
            }
            
            # Run workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            self.logger.info("Tender automation workflow completed")
            
            return {
                "status": "success",
                "results": final_state.get("results", {}),
                "errors": final_state.get("errors", [])
            }
            
        except Exception as e:
            self.logger.error(f"Error in full automation: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def handle_user_query(self, query: str) -> Dict[str, Any]:
        """Handle individual user query"""
        try:
            self.logger.info(f"Processing user query: {query}")
            
            # Initialize state for query handling
            query_state = {
                "current_step": "handle_user_query",
                "user_query": query,
                "results": {},
                "errors": []
            }
            
            # Process query
            response = await self.process_user_query(query)
            
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