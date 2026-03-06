import asyncio
import os
from typing import Dict, Any, List
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta
import re
from agents.base_agent import BaseAgent
from models.schemas import Tender, TenderRequirement, TenderStatus
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PortalMonitorAgent(BaseAgent):
    def __init__(self):
        super().__init__("PortalMonitor")
        self.gem_portal_url = os.getenv('GEM_PORTAL_URL', 'https://bidplus.gem.gov.in/all-bids')
        self.downloads_dir = "downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute portal monitoring task"""
        try:
            self.update_status("monitoring")
            
            search_keyword = task.get("search_keyword", "pump")
            
            self.log_activity(f"Starting GeM portal search for keyword: {search_keyword}")
            
            # Search and download tenders
            tenders = await self.search_and_download_tenders(search_keyword)
            
            self.log_activity(f"Successfully processed {len(tenders)} tenders")
            
            return {
                "status": "success",
                "tenders": tenders,
                "total_found": len(tenders),
                "search_keyword": search_keyword
            }
            
        except Exception as e:
            self.log_activity(f"Error in portal monitoring: {e}", "error")
            return {
                "status": "error",
                "error": str(e),
                "tenders": []
            }
    
    async def search_and_download_tenders(self, keyword: str) -> List[Tender]:
        """Search for tenders and download PDFs by clicking bid numbers"""
        tenders = []
        
        try:
            async with async_playwright() as p:
                # Launch browser
                self.log_activity("Opening browser...")
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Navigate to GeM portal
                self.log_activity(f"Navigating to: {self.gem_portal_url}")
                await page.goto(self.gem_portal_url, wait_until="networkidle")
                
                # Wait for page to load
                await page.wait_for_timeout(5000)
                
                # Take screenshot
                await page.screenshot(path="portal_loaded.png")
                self.log_activity("Portal loaded, screenshot saved")
                
                # Find and use search box
                search_success = await self.perform_search(page, keyword)
                
                if search_success:
                    # Find and click bid number links directly
                    tenders = await self.click_bid_links_and_download(page)
                    self.log_activity(f"Successfully processed {len(tenders)} tenders")
                
                await browser.close()
                
        except Exception as e:
            self.log_activity(f"Error in search and download: {e}", "error")
        
        return tenders
    
    async def click_bid_links_and_download(self, page: Page) -> List[Tender]:
        """Find bid number links and click them to download PDFs"""
        tenders = []
        
        try:
            # Wait for results to load
            await page.wait_for_timeout(3000)
            
            # Find all bid number links (the blue GEM/ links)
            all_links = await page.query_selector_all('a')
            bid_links = []
            
            for link in all_links:
                try:
                    text = await link.text_content()
                    if text and text.strip().startswith('GEM/'):
                        bid_links.append(link)
                        self.log_activity(f"Found bid link: {text.strip()}")
                except:
                    continue
            
            self.log_activity(f"Found {len(bid_links)} bid number links to click")
            
            # Click each bid link and download PDF
            for i, bid_link in enumerate(bid_links[:10]):  # Process first 10 tenders
                try:
                    bid_text = await bid_link.text_content()
                    bid_number = bid_text.strip()
                    
                    self.log_activity(f"Clicking bid {i+1}: {bid_number}")
                    
                    # Set up download listener before clicking
                    filename = f"tender_{i+1}_{bid_number.replace('/', '_')}.pdf"
                    filepath = os.path.join(self.downloads_dir, filename)
                    
                    # Click the bid link and wait for download
                    async with page.expect_download(timeout=15000) as download_info:
                        await bid_link.click()
                    
                    download = await download_info.value
                    await download.save_as(filepath)
                    
                    self.log_activity(f"Successfully downloaded: {filename}")
                    
                    # Create tender object
                    tender = Tender(
                        tender_id=bid_number,
                        title=f"Tender {bid_number}",
                        description=f"Tender from GeM portal: {bid_number}",
                        portal="gem",
                        category="engineering",
                        deadline=datetime.now() + timedelta(days=30),
                        requirements=TenderRequirement(),
                        status=TenderStatus.DISCOVERED,
                        documents_url=f"GeM Bid: {bid_number}",
                        document_path=filepath
                    )
                    
                    tenders.append(tender)
                    
                    # Wait a bit between downloads
                    await page.wait_for_timeout(2000)
                    
                except Exception as e:
                    self.log_activity(f"Error downloading bid {i+1}: {e}", "warning")
                    continue
            
            return tenders
            
        except Exception as e:
            self.log_activity(f"Error in click and download: {e}", "error")
            return []
    
    async def perform_search(self, page: Page, keyword: str) -> bool:
        """Perform search on the portal"""
        try:
            self.log_activity(f"Searching for keyword: {keyword}")
            
            # Look for search input - try the specific ID we found
            search_input = None
            
            # Try different selectors
            selectors = [
                '#searchBid',  # The ID we found in logs
                'input[name="searchBid"]',
                'input[placeholder*="Keyword"]',
                'input[type="search"]'
            ]
            
            for selector in selectors:
                try:
                    search_input = await page.wait_for_selector(selector, timeout=3000)
                    if search_input:
                        self.log_activity(f"Found search input: {selector}")
                        break
                except:
                    continue
            
            if not search_input:
                self.log_activity("Search input not found", "error")
                return False
            
            # Enter search keyword
            await search_input.click()
            await search_input.fill(keyword)
            self.log_activity(f"Entered keyword: {keyword}")
            
            # Submit search
            await page.keyboard.press('Enter')
            self.log_activity("Submitted search")
            
            # Wait for results
            await page.wait_for_timeout(5000)
            
            # Take screenshot after search
            await page.screenshot(path="after_search.png")
            self.log_activity("Search completed, screenshot saved")
            
            return True
            
        except Exception as e:
            self.log_activity(f"Error in search: {e}", "error")
            return False
    
    async def get_tender_by_url(self, tender_url: str) -> Tender:
        """Get specific tender by URL - for manual testing"""
        try:
            # This method can be used for testing specific tender URLs
            # For now, return a basic tender object
            return Tender(
                tender_id=f"MANUAL_{int(datetime.now().timestamp())}",
                title="Manual Tender",
                description="Manually specified tender",
                portal="gem",
                category="engineering",
                deadline=datetime.now() + timedelta(days=30),
                requirements=TenderRequirement(),
                status=TenderStatus.DISCOVERED,
                documents_url=tender_url
            )
                
        except Exception as e:
            self.log_activity(f"Error getting tender from URL: {e}", "error")
            return None