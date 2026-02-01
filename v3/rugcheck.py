"""
RugCheck.xyz API - FREE rug detection
"""
import aiohttp
import asyncio
from typing import Dict, Optional
from loguru import logger


class RugCheck:
    """RugCheck.xyz API wrapper"""

    BASE_URL = "https://api.rugcheck.xyz/v1"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def check(self, token_address: str, timeout: int = 5) -> Dict:
        """
        Check token for rug risk.

        Returns:
            {
                'safe': bool,
                'risk_level': str ('good', 'low', 'medium', 'high', 'critical'),
                'score': float (0-10, lower = safer),
                'is_honeypot': bool,
                'freezeable': bool,
                'reason': str (if blocked)
            }
        """
        await self._ensure_session()

        try:
            url = f"{self.BASE_URL}/tokens/{token_address}/report"
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status == 404:
                    # Token too new - allow it
                    return {'safe': True, 'risk_level': 'unknown', 'reason': 'Not in database'}

                if resp.status != 200:
                    return {'safe': True, 'risk_level': 'unknown', 'reason': f'API error {resp.status}'}

                data = await resp.json()
                return self._parse(data)

        except asyncio.TimeoutError:
            return {'safe': True, 'risk_level': 'unknown', 'reason': 'Timeout'}
        except Exception as e:
            logger.debug(f"RugCheck error: {e}")
            return {'safe': True, 'risk_level': 'unknown', 'reason': str(e)}

    def _parse(self, data: Dict) -> Dict:
        """Parse RugCheck response. Lower score = safer."""
        rugged = data.get('rugged', False)
        score = data.get('score_normalised', data.get('score', 0))
        risks = data.get('risks', [])

        # Check for freeze authority
        freezeable = any('freeze' in r.get('name', '').lower() for r in risks)

        # Determine risk level (score 0-10, lower = better)
        if rugged:
            risk_level = 'critical'
        elif score <= 2:
            risk_level = 'good'
        elif score <= 4:
            risk_level = 'low'
        elif score <= 6:
            risk_level = 'medium'
        elif score <= 8:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        # Block critical/high risk
        safe = risk_level in ('good', 'low', 'medium', 'unknown')
        reason = None
        if not safe:
            if rugged:
                reason = 'Confirmed rug'
            elif freezeable:
                reason = f'Freeze authority (score {score})'
            else:
                reason = f'High risk score {score}'

        return {
            'safe': safe,
            'risk_level': risk_level,
            'score': score,
            'is_honeypot': rugged,
            'freezeable': freezeable,
            'reason': reason
        }


# Singleton
_instance: Optional[RugCheck] = None

def get_rugcheck() -> RugCheck:
    global _instance
    if _instance is None:
        _instance = RugCheck()
    return _instance

async def cleanup_rugcheck():
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
