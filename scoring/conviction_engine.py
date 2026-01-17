"""
Conviction Engine - Calculate conviction scores for tokens
"""
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
import config


class ConvictionEngine:
    """Calculates conviction scores based on multiple signals"""
    
    def __init__(self, smart_wallet_tracker, narrative_detector):
        self.smart_wallet_tracker = smart_wallet_tracker
        self.narrative_detector = narrative_detector
        
    def calculate_conviction(
        self,
        token_address: str,
        symbol: str,
        name: str = '',
        description: str = '',
        age_minutes: int = 0,
        liquidity: float = 0,
        holders: int = 0,
        **kwargs
    ) -> Dict:
        """
        Calculate conviction score for a token
        Returns score breakdown and decision
        """
        
        # Start with base score
        score = 50
        breakdown = {
            'base': 50,
            'smart_wallets': 0,
            'narrative': 0,
            'timing': 0
        }
        reasons = []
        
        # ================================================================
        # 1. SMART WALLET ACTIVITY (Max +40 points)
        # ================================================================
        if config.ENABLE_SMART_WALLETS:
            wallet_data = self.smart_wallet_tracker.get_smart_wallet_activity(token_address)
            
            if wallet_data['has_activity']:
                wallet_score = wallet_data['score']
                breakdown['smart_wallets'] = wallet_score
                score += wallet_score
                
                # Build reason string
                if wallet_data['elite_count'] > 0:
                    reasons.append(f"🏆 {wallet_data['elite_count']} elite wallet{'s' if wallet_data['elite_count'] > 1 else ''}")
                if wallet_data['top_kol_count'] > 0:
                    reasons.append(f"👑 {wallet_data['top_kol_count']} top KOL{'s' if wallet_data['top_kol_count'] > 1 else ''}")
        
        # ================================================================
        # 2. NARRATIVE DETECTION (Max +35 points)
        # ================================================================
        if config.ENABLE_NARRATIVES:
            narrative_data = self.narrative_detector.analyze_token(symbol, name, description)
            
            if narrative_data['has_narrative']:
                narrative_score = narrative_data['score']
                breakdown['narrative'] = narrative_score
                score += narrative_score
                
                # Build reason string
                primary = narrative_data['primary_narrative']
                if primary:
                    reasons.append(f"📈 {primary.upper()} narrative")
                
                if len(narrative_data['narratives']) > 1:
                    reasons.append(f"🎯 Multiple narratives")
        
        # ================================================================
        # 3. TIMING BONUS (Max +10 points)
        # ================================================================
        timing_score = 0
        if age_minutes < 30:
            timing_score = config.WEIGHTS['timing_very_early']
            reasons.append("⚡ Ultra early (<30m)")
        elif age_minutes < 60:
            timing_score = config.WEIGHTS['timing_early']
            reasons.append("🚀 Early entry (<1h)")
        
        breakdown['timing'] = timing_score
        score += timing_score
        
        # ================================================================
        # 4. BASIC QUALITY CHECKS
        # ================================================================
        passes_quality = True
        quality_issues = []
        
        if liquidity < config.MIN_LIQUIDITY:
            passes_quality = False
            quality_issues.append(f"Low liquidity (${liquidity:,.0f})")
        
        if holders < config.MIN_HOLDERS:
            passes_quality = False
            quality_issues.append(f"Few holders ({holders})")
        
        if age_minutes > config.MAX_AGE_MINUTES:
            passes_quality = False
            quality_issues.append(f"Too old ({age_minutes}m)")
        
        # ================================================================
        # 5. FINAL DECISION
        # ================================================================
        should_signal = (
            score >= config.MIN_CONVICTION_SCORE and
            passes_quality
        )
        
        result = {
            'conviction_score': min(score, 100),  # Cap at 100
            'breakdown': breakdown,
            'reasons': reasons,
            'should_signal': should_signal,
            'passes_quality': passes_quality,
            'quality_issues': quality_issues,
            'meets_threshold': score >= config.MIN_CONVICTION_SCORE
        }
        
        # Log decision
        if should_signal:
            logger.info(f"✅ HIGH CONVICTION: {symbol} - Score: {score}/100")
            for reason in reasons:
                logger.info(f"   {reason}")
        else:
            logger.debug(f"❌ Low conviction: {symbol} - Score: {score}/100 (threshold: {config.MIN_CONVICTION_SCORE})")
            if quality_issues:
                for issue in quality_issues:
                    logger.debug(f"   ⚠️ {issue}")
        
        return result
    
    def get_scoring_summary(self) -> str:
        """Get a human-readable explanation of the scoring system"""
        return f"""
📊 CONVICTION SCORING SYSTEM

Base Score: 50 points

🏆 Smart Wallet Activity (Max +40):
  • Elite wallet buy: +{config.WEIGHTS['smart_wallet_elite']} each
  • Top KOL buy: +{config.WEIGHTS['smart_wallet_kol']} each

📈 Narrative Matching (Max +35):
  • Hot narrative: +{config.WEIGHTS['narrative_hot']}
  • Fresh narrative: +{config.WEIGHTS['narrative_fresh']}
  • Multiple narratives: +{config.WEIGHTS['narrative_multiple']}

⚡ Timing Bonus (Max +10):
  • Ultra early (<30m): +{config.WEIGHTS['timing_very_early']}
  • Early (30-60m): +{config.WEIGHTS['timing_early']}

📋 Quality Filters:
  • Min liquidity: ${config.MIN_LIQUIDITY:,}
  • Min holders: {config.MIN_HOLDERS}
  • Max age: {config.MAX_AGE_MINUTES} minutes

🎯 Signal Threshold: {config.MIN_CONVICTION_SCORE}/100
        """.strip()
