import asyncio
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from models.schemas import UserProfile, TenderRequirement, EligibilityResult, EligibilityStatus, Tender
import logging
import re

class EligibilityMatcherAgent(BaseAgent):
    def __init__(self):
        super().__init__("EligibilityMatcher")
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute eligibility matching task"""
        try:
            self.update_status("matching")
            
            tender = task.get("tender")
            user_profile = task.get("user_profile")
            requirements = task.get("requirements")
            
            if not all([tender, user_profile, requirements]):
                return {
                    "status": "error",
                    "error": "Missing required data for eligibility matching",
                    "eligibility_result": None
                }
            
            self.log_activity(f"Checking eligibility for tender: {tender.title[:50]}...")
            
            # Perform eligibility check
            eligibility_result = await self.check_eligibility(tender, user_profile, requirements)
            
            self.log_activity(f"Eligibility check completed: {eligibility_result.status.value}")
            
            return {
                "status": "success",
                "eligibility_result": eligibility_result,
                "match_score": eligibility_result.match_score
            }
            
        except Exception as e:
            self.log_activity(f"Error in eligibility matching: {e}", "error")
            return {
                "status": "error",
                "error": str(e),
                "eligibility_result": None
            }
    
    async def check_eligibility(self, tender: Tender, user_profile: UserProfile, requirements: TenderRequirement) -> EligibilityResult:
        """Check eligibility against all criteria"""
        try:
            met_criteria = []
            missing_criteria = []
            reasons = []
            gaps = []
            recommendations = []
            
            total_checks = 0
            passed_checks = 0
            
            # CRITICAL: Check MSME/Startup relaxation FIRST
            if requirements.msme_relaxation and user_profile.is_msme:
                reasons.append("🎯 MSME relaxation applied - turnover and experience requirements waived")
                met_criteria.append("MSME relaxation available and applicable")
                self.log_activity("MSME relaxation applied - skipping turnover and experience checks")
                
                # Skip turnover and experience checks for MSME
                turnover_waived = True
                experience_waived = True
            elif requirements.startup_relaxation and user_profile.is_startup:
                reasons.append("🎯 Startup relaxation applied - turnover and experience requirements waived")
                met_criteria.append("Startup relaxation available and applicable")
                self.log_activity("Startup relaxation applied - skipping turnover and experience checks")
                
                # Skip turnover and experience checks for Startup
                turnover_waived = True
                experience_waived = True
            else:
                turnover_waived = False
                experience_waived = False
                if requirements.msme_relaxation or requirements.startup_relaxation:
                    reasons.append("⚠️ Relaxation available but company doesn't qualify (not MSME/Startup)")
            
            # Check EMD requirement
            if requirements.emd_required:
                total_checks += 1
                if user_profile.can_pay_emd:
                    if requirements.emd_amount and user_profile.max_emd_amount:
                        if user_profile.max_emd_amount >= requirements.emd_amount:
                            passed_checks += 1
                            met_criteria.append(f"EMD requirement met: Can provide ₹{requirements.emd_amount} lakhs")
                            reasons.append(f"✅ Company can provide required EMD (₹{requirements.emd_amount}L)")
                        else:
                            missing_criteria.append(f"EMD amount too high: ₹{requirements.emd_amount} lakhs required, company can provide ₹{user_profile.max_emd_amount} lakhs")
                            reasons.append(f"❌ EMD amount too high (₹{requirements.emd_amount}L required, can provide ₹{user_profile.max_emd_amount}L)")
                            gaps.append(f"Increase EMD capability by ₹{requirements.emd_amount - user_profile.max_emd_amount} lakhs")
                    else:
                        passed_checks += 1
                        met_criteria.append("EMD requirement met: Company can provide EMD")
                        reasons.append("✅ Company can provide required EMD")
                else:
                    missing_criteria.append("EMD required but company cannot provide")
                    reasons.append("❌ EMD required but company cannot provide EMD")
                    gaps.append("Arrange for EMD provision capability")
                    recommendations.append("Set up EMD provision through bank guarantee or fixed deposit")
            
            # Check minimum turnover (only if not waived)
            if requirements.min_turnover and not turnover_waived:
                total_checks += 1
                if user_profile.annual_turnover >= requirements.min_turnover:
                    passed_checks += 1
                    met_criteria.append(f"Turnover requirement met: ₹{user_profile.annual_turnover} lakhs >= ₹{requirements.min_turnover} lakhs")
                    reasons.append(f"✅ Company turnover (₹{user_profile.annual_turnover}L) meets minimum requirement (₹{requirements.min_turnover}L)")
                else:
                    missing_criteria.append(f"Minimum turnover: ₹{requirements.min_turnover} lakhs required, company has ₹{user_profile.annual_turnover} lakhs")
                    reasons.append(f"❌ Company turnover (₹{user_profile.annual_turnover}L) below minimum requirement (₹{requirements.min_turnover}L)")
                    gaps.append(f"Increase annual turnover by ₹{requirements.min_turnover - user_profile.annual_turnover} lakhs")
                    recommendations.append("Consider partnering with other companies or wait for business growth")
            
            # Check minimum experience (only if not waived)
            if requirements.min_experience and not experience_waived:
                total_checks += 1
                if user_profile.experience_years >= requirements.min_experience:
                    passed_checks += 1
                    met_criteria.append(f"Experience requirement met: {user_profile.experience_years} years >= {requirements.min_experience} years")
                    reasons.append(f"✅ Company experience ({user_profile.experience_years} years) meets minimum requirement ({requirements.min_experience} years)")
                else:
                    missing_criteria.append(f"Minimum experience: {requirements.min_experience} years required, company has {user_profile.experience_years} years")
                    reasons.append(f"❌ Company experience ({user_profile.experience_years} years) below minimum requirement ({requirements.min_experience} years)")
                    gaps.append(f"Need {requirements.min_experience - user_profile.experience_years} more years of experience")
                    recommendations.append("Consider joint ventures with experienced companies")
            
            # Check required certifications
            if requirements.required_certifications:
                total_checks += 1
                # Fix the potential None bug
                user_certs = (user_profile.iso_certifications or []) + (user_profile.other_certifications or [])
                user_certs_lower = [cert.lower() for cert in user_certs]
                required_certs_lower = [cert.lower() for cert in requirements.required_certifications]
                
                missing_certs = []
                found_certs = []
                
                for req_cert in required_certs_lower:
                    found = False
                    for user_cert in user_certs_lower:
                        if req_cert in user_cert or user_cert in req_cert:
                            found_certs.append(req_cert)
                            found = True
                            break
                    if not found:
                        missing_certs.append(req_cert)
                
                if not missing_certs:
                    passed_checks += 1
                    met_criteria.append(f"All required certifications available: {', '.join(found_certs)}")
                    reasons.append(f"✅ All required certifications available")
                else:
                    missing_criteria.append(f"Missing certifications: {', '.join(missing_certs)}")
                    reasons.append(f"❌ Missing certifications: {', '.join(missing_certs)}")
                    gaps.extend([f"Obtain {cert} certification" for cert in missing_certs])
                    recommendations.append("Apply for required certifications through authorized bodies")
            
            # Check location requirements
            if requirements.required_location or requirements.required_state:
                total_checks += 1
                location_match = False
                
                user_location_lower = user_profile.location.lower()
                user_state_lower = user_profile.state.lower() if hasattr(user_profile, 'state') else ""
                
                if requirements.required_location:
                    req_location_lower = requirements.required_location.lower()
                    if req_location_lower in user_location_lower or user_location_lower in req_location_lower:
                        location_match = True
                
                if requirements.required_state:
                    req_state_lower = requirements.required_state.lower()
                    if req_state_lower in user_state_lower or user_state_lower in req_state_lower:
                        location_match = True
                
                if location_match:
                    passed_checks += 1
                    met_criteria.append(f"Location requirement met: {user_profile.location}")
                    reasons.append(f"✅ Company location matches requirement")
                else:
                    missing_criteria.append(f"Location requirement not met")
                    reasons.append(f"❌ Company location ({user_profile.location}) doesn't match requirement")
                    gaps.append("Company not in required location/state")
                    recommendations.append("Consider establishing presence in required location")
            
            # Check sector requirements
            if requirements.sector_restrictions:
                total_checks += 1
                user_sectors_lower = [sector.lower() for sector in user_profile.business_sectors]
                required_sectors_lower = [sector.lower() for sector in requirements.sector_restrictions]
                
                sector_match = False
                for req_sector in required_sectors_lower:
                    for user_sector in user_sectors_lower:
                        if req_sector in user_sector or user_sector in req_sector:
                            sector_match = True
                            break
                    if sector_match:
                        break
                
                if sector_match:
                    passed_checks += 1
                    met_criteria.append(f"Sector requirement met")
                    reasons.append(f"✅ Company operates in required sector")
                else:
                    missing_criteria.append(f"Sector requirement not met")
                    reasons.append(f"❌ Company sector doesn't match requirement")
                    gaps.append("Company not in required business sector")
                    recommendations.append("Consider expanding business to required sectors")
            
            # Calculate match score
            if total_checks > 0:
                match_score = (passed_checks / total_checks) * 100
            else:
                match_score = 100  # If no specific requirements, assume eligible
                reasons.append("ℹ️ No specific eligibility criteria found in tender document")
            
            # Determine eligibility status
            if match_score >= 100:
                status = EligibilityStatus.ELIGIBLE
            elif match_score >= 70:
                status = EligibilityStatus.PARTIALLY_ELIGIBLE
            else:
                status = EligibilityStatus.NOT_ELIGIBLE
            
            # Add summary reason
            if status == EligibilityStatus.ELIGIBLE:
                reasons.insert(0, f"🎯 Company meets all requirements for this tender")
            elif status == EligibilityStatus.PARTIALLY_ELIGIBLE:
                reasons.insert(0, f"⚠️ Company meets most requirements but has some gaps")
            else:
                reasons.insert(0, f"❌ Company does not meet minimum requirements for this tender")
            
            eligibility_result = EligibilityResult(
                status=status,
                match_score=round(match_score, 1),
                reasons=reasons,
                met_criteria=met_criteria,
                missing_criteria=missing_criteria,
                gaps=gaps,
                recommendations=recommendations
            )
            
            self.log_activity(f"Eligibility analysis completed: {status.value} ({match_score:.1f}%)")
            
            return eligibility_result
            
        except Exception as e:
            self.log_activity(f"Error checking eligibility: {e}", "error")
            return EligibilityResult(
                status=EligibilityStatus.NOT_ELIGIBLE,
                match_score=0.0,
                reasons=[f"Error in eligibility analysis: {str(e)}"],
                met_criteria=[],
                missing_criteria=[],
                gaps=[],
                recommendations=[]
            )
    
    async def get_eligibility_summary(self, eligibility_result: EligibilityResult) -> str:
        """Get a concise eligibility summary"""
        try:
            status_emoji = {
                EligibilityStatus.ELIGIBLE: "✅",
                EligibilityStatus.PARTIALLY_ELIGIBLE: "⚠️",
                EligibilityStatus.NOT_ELIGIBLE: "❌"
            }
            
            emoji = status_emoji.get(eligibility_result.status, "❓")
            
            summary = f"{emoji} {eligibility_result.status.value} ({eligibility_result.match_score}%)\n\n"
            
            if eligibility_result.reasons:
                summary += "Key Points:\n"
                for reason in eligibility_result.reasons[:3]:
                    summary += f"• {reason}\n"
            
            if eligibility_result.gaps:
                summary += f"\nGaps to Address:\n"
                for gap in eligibility_result.gaps[:3]:
                    summary += f"• {gap}\n"
            
            return summary
            
        except Exception as e:
            self.log_activity(f"Error creating eligibility summary: {e}", "error")
            return f"Error creating summary: {str(e)}"
    
    async def compare_multiple_tenders(self, tenders: List[Tender], user_profile: UserProfile) -> List[Dict[str, Any]]:
        """Compare eligibility across multiple tenders"""
        try:
            results = []
            
            for tender in tenders:
                if hasattr(tender, 'requirements') and tender.requirements:
                    eligibility = await self.check_eligibility(tender, user_profile, tender.requirements)
                    results.append({
                        "tender": tender,
                        "eligibility": eligibility,
                        "priority": self.calculate_priority(tender, eligibility)
                    })
            
            # Sort by priority (highest first)
            results.sort(key=lambda x: x["priority"], reverse=True)
            
            return results
            
        except Exception as e:
            self.log_activity(f"Error comparing multiple tenders: {e}", "error")
            return []
    
    def calculate_priority(self, tender: Tender, eligibility: EligibilityResult) -> float:
        """Calculate priority score for tender"""
        try:
            priority = eligibility.match_score
            
            # Boost priority for eligible tenders
            if eligibility.status == EligibilityStatus.ELIGIBLE:
                priority += 20
            elif eligibility.status == EligibilityStatus.PARTIALLY_ELIGIBLE:
                priority += 10
            
            # Consider deadline urgency
            from datetime import datetime, timedelta
            days_remaining = (tender.deadline - datetime.now()).days
            if days_remaining <= 7:
                priority += 15  # Urgent
            elif days_remaining <= 30:
                priority += 5   # Soon
            
            # Consider tender value if available
            if tender.estimated_value:
                if tender.estimated_value > 100:  # > 1 crore
                    priority += 10
                elif tender.estimated_value > 50:  # > 50 lakhs
                    priority += 5
            
            return min(priority, 150)  # Cap at 150
            
        except Exception as e:
            self.log_activity(f"Error calculating priority: {e}", "error")
            return eligibility.match_score