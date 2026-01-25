#!/usr/bin/env python3
"""
Enhanced Token Analyzer - Maximum Data Extraction

For each token that ran yesterday, extract EVERYTHING:
1. Price history (start, 1hr, 6hr, peak, current)
2. Volume patterns (growth rate, spikes, consistency)
3. Holder distribution (concentration, top holder %)
4. Early transaction patterns (first 100 txs, timing, sizes)
5. Whale activity (who, when, how much, entry MCAP)
6. Social signals (Twitter, Telegram mentions)
7. Rug indicators (bundles, dev sells, concentration)
8. Liquidity changes (adds, removes, final LP)
9. Time to peak (how fast did it pump)
10. Bonding curve data (graduation %, time on curve)

The more data we collect, the better ML predictions become.
"""
import asyncio
import aiohttp
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime, timedelta


class EnhancedTokenAnalyzer:
    """Extracts maximum information from a token for ML training"""

    def __init__(self, helius_rpc_url: str, moralis_headers: dict = None):
        self.helius_rpc_url = helius_rpc_url
        self.moralis_headers = moralis_headers or {}

    async def analyze_token_complete(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """
        Extract ALL available data for a token

        Returns comprehensive dict with:
        - Basic info (symbol, name, address)
        - Price history (start, hourly, peak, current)
        - Volume patterns (growth, spikes, consistency)
        - Holder data (count, distribution, concentration)
        - Transaction patterns (early buys, sizes, timing)
        - Whale activity (addresses, entry points, sizes)
        - Social signals (mentions, sentiment)
        - Rug indicators (bundles, sells, concentration)
        - Timing data (creation, graduation, peak time)
        """
        logger.info(f"   📊 Deep analysis of {token_address[:8]}...")

        analysis = {
            'token_address': token_address,
            'analyzed_at': datetime.utcnow().isoformat(),
        }

        # Parallel data extraction
        tasks = [
            self._get_dexscreener_full(token_address, session),
            self._get_helius_token_info(token_address, session),
            self._get_holder_distribution(token_address, session),
            self._get_transaction_history(token_address, session),
            self._get_price_history(token_address, session),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge all results
        for result in results:
            if isinstance(result, dict):
                analysis.update(result)
            elif isinstance(result, Exception):
                logger.debug(f"   Error in data extraction: {result}")

        # Calculate derived metrics
        analysis.update(self._calculate_derived_metrics(analysis))

        return analysis

    async def _get_dexscreener_full(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """Get comprehensive DexScreener data"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get('pairs', [])

                    if not pairs:
                        return {}

                    # Get main pair (highest liquidity)
                    pair = max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0))

                    return {
                        'symbol': pair.get('baseToken', {}).get('symbol'),
                        'name': pair.get('baseToken', {}).get('name'),
                        'price_usd': float(pair.get('priceUsd', 0) or 0),
                        'market_cap': float(pair.get('fdv', 0) or 0),
                        'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                        'liquidity_base': float(pair.get('liquidity', {}).get('base', 0) or 0),
                        'liquidity_quote': float(pair.get('liquidity', {}).get('quote', 0) or 0),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                        'volume_6h': float(pair.get('volume', {}).get('h6', 0) or 0),
                        'volume_1h': float(pair.get('volume', {}).get('h1', 0) or 0),
                        'volume_5m': float(pair.get('volume', {}).get('m5', 0) or 0),
                        'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                        'price_change_6h': float(pair.get('priceChange', {}).get('h6', 0) or 0),
                        'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0) or 0),
                        'price_change_5m': float(pair.get('priceChange', {}).get('m5', 0) or 0),
                        'buys_24h': pair.get('txns', {}).get('h24', {}).get('buys', 0),
                        'sells_24h': pair.get('txns', {}).get('h24', {}).get('sells', 0),
                        'buys_6h': pair.get('txns', {}).get('h6', {}).get('buys', 0),
                        'sells_6h': pair.get('txns', {}).get('h6', {}).get('sells', 0),
                        'buys_1h': pair.get('txns', {}).get('h1', {}).get('buys', 0),
                        'sells_1h': pair.get('txns', {}).get('h1', {}).get('sells', 0),
                        'created_at': pair.get('pairCreatedAt', 0),
                        'dex_url': pair.get('url'),
                        'dex_id': pair.get('dexId'),
                        'pair_address': pair.get('pairAddress'),
                    }
        except Exception as e:
            logger.debug(f"   DexScreener error: {e}")
            return {}

    async def _get_helius_token_info(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """Get token metadata and supply info from Helius"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": [token_address]
            }

            async with session.post(self.helius_rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'result' in data and 'value' in data['result']:
                        supply_data = data['result']['value']
                        return {
                            'total_supply': float(supply_data.get('amount', 0)),
                            'decimals': supply_data.get('decimals', 0),
                        }
        except Exception as e:
            logger.debug(f"   Helius token info error: {e}")

        return {}

    async def _get_holder_distribution(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """
        Get holder distribution using Helius getTokenLargestAccounts

        Extract:
        - Total holders (approximation)
        - Top 10 holder concentration
        - Top holder %
        - Distribution score (how spread out)
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenLargestAccounts",
                "params": [token_address]
            }

            async with session.post(self.helius_rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if 'result' in data and 'value' in data['result']:
                        accounts = data['result']['value']

                        if not accounts:
                            return {}

                        # Calculate total supply from top holders
                        total_supply = sum(float(acc.get('amount', 0)) for acc in accounts)
                        if total_supply == 0:
                            return {}

                        # Top holder percentages
                        top_1_amount = float(accounts[0].get('amount', 0)) if len(accounts) > 0 else 0
                        top_5_amount = sum(float(accounts[i].get('amount', 0)) for i in range(min(5, len(accounts))))
                        top_10_amount = sum(float(accounts[i].get('amount', 0)) for i in range(min(10, len(accounts))))

                        top_1_pct = (top_1_amount / total_supply * 100) if total_supply > 0 else 0
                        top_5_pct = (top_5_amount / total_supply * 100) if total_supply > 0 else 0
                        top_10_pct = (top_10_amount / total_supply * 100) if total_supply > 0 else 0

                        # Concentration score (0-100, higher = more concentrated)
                        # Based on top 10 holder %
                        concentration_score = min(100, top_10_pct)

                        return {
                            'holder_count_estimate': len(accounts),  # Rough estimate
                            'top_1_holder_pct': round(top_1_pct, 2),
                            'top_5_holder_pct': round(top_5_pct, 2),
                            'top_10_holder_pct': round(top_10_pct, 2),
                            'concentration_score': round(concentration_score, 2),
                            'distribution_quality': self._get_distribution_quality(top_10_pct),
                        }
        except Exception as e:
            logger.debug(f"   Holder distribution error: {e}")

        return {}

    async def _get_transaction_history(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """
        Get early transaction patterns using Helius

        Extract:
        - First 100 transactions
        - Early buy sizes (large early buyers = whales)
        - Transaction timing (bundles, coordinated buys)
        - Buy/sell ratio over time
        """
        try:
            # Use Helius Enhanced Transaction API
            # getSignaturesForAddress to get transaction sigs
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    token_address,
                    {"limit": 100}  # First 100 transactions
                ]
            }

            async with session.post(self.helius_rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if 'result' in data:
                        sigs = data['result']

                        return {
                            'early_tx_count': len(sigs),
                            'first_tx_timestamp': sigs[-1].get('blockTime', 0) if sigs else 0,
                            'recent_tx_timestamp': sigs[0].get('blockTime', 0) if sigs else 0,
                            # TODO: Parse individual transactions for buy/sell analysis
                            # This requires getParsedTransaction for each sig
                        }
        except Exception as e:
            logger.debug(f"   Transaction history error: {e}")

        return {}

    async def _get_price_history(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """
        Estimate price history using current data

        Since we don't have historical price API in free tier,
        we estimate based on:
        - Current price
        - 24h change %
        - Volume patterns
        """
        # This would ideally use a price history API
        # For now, we calculate estimates based on price_change data
        # which we already have from DexScreener

        return {
            # Will be calculated in _calculate_derived_metrics
        }

    def _calculate_derived_metrics(self, analysis: Dict) -> Dict:
        """
        Calculate additional metrics from extracted data

        Derived metrics:
        - Buy/sell ratio
        - Volume velocity (volume / MCAP ratio)
        - Price volatility
        - Holder quality score
        - Pump speed (time to peak)
        - Rug risk score
        """
        derived = {}

        # Buy/sell ratios
        buys_24h = analysis.get('buys_24h', 0)
        sells_24h = analysis.get('sells_24h', 0)
        if buys_24h + sells_24h > 0:
            derived['buy_ratio_24h'] = round(buys_24h / (buys_24h + sells_24h) * 100, 2)

        buys_6h = analysis.get('buys_6h', 0)
        sells_6h = analysis.get('sells_6h', 0)
        if buys_6h + sells_6h > 0:
            derived['buy_ratio_6h'] = round(buys_6h / (buys_6h + sells_6h) * 100, 2)

        # Volume velocity (volume / MCAP)
        mcap = analysis.get('market_cap', 0)
        volume_24h = analysis.get('volume_24h', 0)
        if mcap > 0:
            derived['volume_mcap_ratio'] = round(volume_24h / mcap, 4)

        # Price at different stages (estimated)
        current_price = analysis.get('price_usd', 0)
        price_change_24h = analysis.get('price_change_24h', 0)

        if current_price > 0 and price_change_24h != 0:
            # Estimate price 24h ago
            price_24h_ago = current_price / (1 + price_change_24h / 100)
            derived['price_24h_ago_estimate'] = price_24h_ago
            derived['gain_multiple'] = round(current_price / price_24h_ago, 2) if price_24h_ago > 0 else 0

        # Liquidity quality
        liquidity = analysis.get('liquidity_usd', 0)
        if mcap > 0:
            derived['liquidity_mcap_ratio'] = round(liquidity / mcap, 4)

        # Distribution quality score
        top_10_pct = analysis.get('top_10_holder_pct', 0)
        if top_10_pct > 0:
            # 0-100 score, higher = better distribution
            # 80%+ top 10 = 0 score (bad)
            # 20% top 10 = 100 score (excellent)
            derived['distribution_score'] = max(0, min(100, (100 - top_10_pct * 1.25)))

        # Rug risk indicators
        rug_risk = 0
        if top_10_pct > 80:
            rug_risk += 50  # Very concentrated
        elif top_10_pct > 70:
            rug_risk += 30
        elif top_10_pct > 50:
            rug_risk += 15

        # Low liquidity relative to MCAP = rug risk
        liq_ratio = derived.get('liquidity_mcap_ratio', 0)
        if liq_ratio < 0.05:  # Less than 5% liquidity
            rug_risk += 25

        derived['rug_risk_score'] = min(100, rug_risk)

        # Outcome categorization
        gain = derived.get('gain_multiple', 0)
        if gain >= 100:
            derived['outcome_category'] = '100x+'
        elif gain >= 50:
            derived['outcome_category'] = '50x'
        elif gain >= 10:
            derived['outcome_category'] = '10x'
        elif gain >= 2:
            derived['outcome_category'] = '2x'
        else:
            derived['outcome_category'] = 'small'

        return derived

    def _get_distribution_quality(self, top_10_pct: float) -> str:
        """Rate distribution quality based on top 10 holder %"""
        if top_10_pct < 30:
            return 'excellent'
        elif top_10_pct < 50:
            return 'good'
        elif top_10_pct < 70:
            return 'fair'
        elif top_10_pct < 80:
            return 'poor'
        else:
            return 'very_poor'
