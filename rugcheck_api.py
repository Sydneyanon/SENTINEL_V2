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

        RugCheck API returns various risk indicators - we aggregate them
        into a simple score and risk level
        """
        try:
            # Extract key fields (adjust based on actual API response)
            score = data.get('score', 50)  # Default to medium if unknown
            risks = data.get('risks', [])

            # Check for critical indicators
            is_honeypot = data.get('isHoneypot', False)
            mutable_metadata = data.get('mutableMetadata', False) or data.get('isMutable', False)
            freezeable = data.get('freezeable', False) or data.get('canFreeze', False)

            # Check top holder concentration
            top_holder_pct = data.get('topHolderPercent', 0)
            if top_holder_pct == 0:
                # Try alternate field names
                top_holder_pct = data.get('top_holder_pct', 0)

            # Count critical risks
            critical_risks = [r for r in risks if r.get('level') == 'critical' or r.get('severity') == 'critical']
            high_risks = [r for r in risks if r.get('level') == 'high' or r.get('severity') == 'high']

            # Determine risk level based on indicators
            if is_honeypot or len(critical_risks) >= 2:
                risk_level = 'critical'  # Likely rug - block
            elif mutable_metadata or freezeable or len(critical_risks) == 1:
                risk_level = 'high'  # High risk - major penalty
            elif len(high_risks) >= 2 or top_holder_pct > 50:
                risk_level = 'medium'  # Moderate risk - penalty
            elif len(high_risks) == 1 or top_holder_pct > 30:
                risk_level = 'low'  # Some risk - small penalty
            else:
                risk_level = 'good'  # Clean - no penalty

            # Override with RugCheck's score if available
            if score is not None:
                if score >= 80:
                    risk_level = 'good'
                elif score >= 60:
                    risk_level = 'low'
                elif score >= 40:
                    risk_level = 'medium'
                elif score >= 20:
                    risk_level = 'high'
                else:
                    risk_level = 'critical'

            return {
                'success': True,
                'score': score,
                'risk_level': risk_level,
                'is_honeypot': is_honeypot,
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
