"""
RugCheck.xyz API Integration
FREE API to check tokens for rug risk before signaling

API Docs: https://api.rugcheck.xyz/
"""
import aiohttp
from typing import Dict, Optional
from loguru import logger
import asyncio


class RugCheckAPI:
    """Lightweight wrapper for RugCheck.xyz API (FREE tier)"""

    BASE_URL = "https://api.rugcheck.xyz/v1"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def check_token(self, token_address: str, timeout: int = 8) -> Dict:
        """
        Check token for rug risk using RugCheck.xyz API

        Args:
            token_address: Solana token mint address
            timeout: Request timeout in seconds (default 8s for speed)

        Returns:
            Dict with rug check results:
            {
                'success': bool,
                'score': int (0-100, higher = safer),
                'risk_level': str ('good', 'low', 'medium', 'high', 'critical'),
                'is_honeypot': bool,
                'mutable_metadata': bool,
                'freezeable': bool,
                'top_holder_pct': float,
                'risks': list of risk objects,
                'critical_risks': list of critical risks,
                'error': str (if failed)
            }
        """
        await self._ensure_session()

        try:
            url = f"{self.BASE_URL}/tokens/{token_address}/report"

            async with self.session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract key metrics from RugCheck response
                    # Note: Actual API response structure may vary - adjust based on real responses
                    return self._parse_rugcheck_response(data)

                elif response.status == 404:
                    # Token not found - likely too new
                    logger.debug(f"   ⚠️  RugCheck: Token not found (too new?)")
                    return {
                        'success': False,
                        'error': 'Token not found in RugCheck database',
                        'score': None,
                        'risk_level': 'unknown'
                    }
                else:
                    logger.warning(f"   ⚠️  RugCheck API error: {response.status}")
                    return {
                        'success': False,
                        'error': f'API returned {response.status}',
                        'score': None,
                        'risk_level': 'unknown'
                    }

        except asyncio.TimeoutError:
            logger.debug(f"   ⚠️  RugCheck timeout (>{timeout}s)")
            return {
                'success': False,
                'error': 'API timeout',
                'score': None,
                'risk_level': 'unknown'
            }
        except Exception as e:
            logger.debug(f"   ⚠️  RugCheck error: {e}")
            return {
                'success': False,
                'error': str(e),
                'score': None,
                'risk_level': 'unknown'
            }

    def _parse_rugcheck_response(self, data: Dict) -> Dict:
        """
        Parse RugCheck API response into our format

        RugCheck scoring (HIGHER = WORSE):
        - score: 0-1000+ (lower is better, 0 = perfect)
        - score_normalised: 0-10 (lower is better, 0 = perfect)
        - rugged: boolean (true = confirmed rug)
        """
        try:
            # RugCheck uses score_normalised (0-10 scale, lower = better)
            score_normalised = data.get('score_normalised', None)
            score_raw = data.get('score', None)
            rugged = data.get('rugged', False)
            risks = data.get('risks', [])

            # Check for critical indicators
            is_honeypot = rugged  # Use rugged flag as honeypot indicator

            # Check metadata mutability from risks
            mutable_metadata = False
            freezeable = False
            for risk in risks:
                if 'mutable' in risk.get('name', '').lower():
                    mutable_metadata = True
                if 'freeze' in risk.get('name', '').lower():
                    freezeable = True

            # Get top holder percentage from topHolders
            top_holder_pct = 0
            top_holders = data.get('topHolders', [])
            if top_holders:
                top_holder_pct = top_holders[0].get('pct', 0)

            # Count critical/danger risks
            critical_risks = [r for r in risks if r.get('level') in ['critical', 'danger', 'error']]
            high_risks = [r for r in risks if r.get('level') in ['warn', 'warning']]

            # Determine risk level using score_normalised (0-10 scale)
            # IMPORTANT: Lower score = better (opposite of typical scoring!)
            if rugged or is_honeypot:
                risk_level = 'critical'  # Confirmed rug - BLOCK
            elif score_normalised is not None:
                # Use normalized score (0-10, lower = better)
                if score_normalised <= 2:
                    risk_level = 'good'      # 0-2 = very safe
                elif score_normalised <= 4:
                    risk_level = 'low'       # 3-4 = low risk
                elif score_normalised <= 6:
                    risk_level = 'medium'    # 5-6 = moderate risk
                elif score_normalised <= 8:
                    risk_level = 'high'      # 7-8 = high risk
                else:
                    risk_level = 'critical'  # 9-10 = very high risk
            elif score_raw is not None:
                # Fallback to raw score (0-1000+, lower = better)
                if score_raw <= 50:
                    risk_level = 'good'
                elif score_raw <= 100:
                    risk_level = 'low'
                elif score_raw <= 200:
                    risk_level = 'medium'
                elif score_raw <= 400:
                    risk_level = 'high'
                else:
                    risk_level = 'critical'
            elif len(critical_risks) >= 2:
                risk_level = 'critical'  # Multiple critical risks
            elif len(critical_risks) == 1:
                risk_level = 'high'  # One critical risk
            elif len(high_risks) >= 3:
                risk_level = 'medium'  # Multiple warnings
            else:
                risk_level = 'good'  # No significant risks

            return {
                'success': True,
                'score': score_normalised if score_normalised is not None else score_raw,
                'score_normalised': score_normalised,
                'score_raw': score_raw,
                'risk_level': risk_level,
                'is_honeypot': is_honeypot,
                'rugged': rugged,
                'mutable_metadata': mutable_metadata,
                'freezeable': freezeable,
                'top_holder_pct': top_holder_pct,
                'risks': risks,
                'critical_risks': critical_risks,
                'risk_count': len(risks),
                'raw_data': data  # Include full response for debugging
            }

        except Exception as e:
            logger.error(f"❌ Error parsing RugCheck response: {e}")
            return {
                'success': False,
                'error': f'Parse error: {e}',
                'score': None,
                'risk_level': 'unknown'
            }


# Singleton instance
_rugcheck_instance: Optional[RugCheckAPI] = None


def get_rugcheck_api() -> RugCheckAPI:
    """Get or create singleton RugCheck API instance"""
    global _rugcheck_instance
    if _rugcheck_instance is None:
        _rugcheck_instance = RugCheckAPI()
    return _rugcheck_instance


async def cleanup_rugcheck_api():
    """Cleanup singleton instance (call on shutdown)"""
    global _rugcheck_instance
    if _rugcheck_instance:
        await _rugcheck_instance.close()
        _rugcheck_instance = None
