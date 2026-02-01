"""
SENTINEL V3 - Data Fetchers
PumpPortal for pre-grad, DexScreener for post-grad.
"""
import aiohttp
from loguru import logger
from typing import Optional, Dict


async def fetch_token_data(token_address: str) -> Optional[Dict]:
    """
    Fetch token data from appropriate source.
    Tries DexScreener first (graduated), falls back to PumpPortal (pre-grad).
    """
    # Try DexScreener first (post-grad)
    dex_data = await fetch_dexscreener(token_address)

    # Only use DexScreener if we have BOTH price AND liquidity
    # Pre-grad tokens often show on DexScreener with price but $0 liquidity
    if dex_data and dex_data.get('price', 0) > 0 and dex_data.get('liquidity', 0) > 0:
        dex_data['source'] = 'dexscreener'
        dex_data['graduated'] = True
        logger.debug(f"Using DexScreener for {dex_data.get('symbol')}: ${dex_data.get('liquidity', 0):,.0f} liq")
        return dex_data

    # Fall back to PumpPortal (pre-grad / bonding curve)
    pump_data = await fetch_pumpportal(token_address)
    if pump_data:
        pump_data['source'] = 'pumpportal'
        pump_data['graduated'] = False
        logger.debug(f"Using PumpPortal for {pump_data.get('symbol')}: ${pump_data.get('liquidity', 0):,.0f} liq")
        return pump_data

    # Last resort: use DexScreener even with $0 liquidity (better than nothing)
    if dex_data and dex_data.get('price', 0) > 0:
        dex_data['source'] = 'dexscreener'
        dex_data['graduated'] = False  # Mark as not graduated if no liquidity
        logger.debug(f"Fallback DexScreener for {dex_data.get('symbol')}: no liquidity data")
        return dex_data

    return None


async def fetch_dexscreener(token_address: str) -> Optional[Dict]:
    """Fetch from DexScreener (graduated tokens on Raydium)."""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                pairs = data.get('pairs', [])

                if not pairs:
                    return None

                # Get Raydium pair with highest liquidity
                raydium_pairs = [p for p in pairs if p.get('dexId') == 'raydium']
                if raydium_pairs:
                    pair = max(raydium_pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                else:
                    pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))

                # Extract transaction counts (buys/sells)
                txns = pair.get('txns', {})
                buys_1h = int(txns.get('h1', {}).get('buys', 0) or 0)
                sells_1h = int(txns.get('h1', {}).get('sells', 0) or 0)
                buys_24h = int(txns.get('h24', {}).get('buys', 0) or 0)
                sells_24h = int(txns.get('h24', {}).get('sells', 0) or 0)

                # Get holder count - try holderCount field or use unique 24h traders as proxy
                holders = int(pair.get('holderCount', 0) or 0)
                if holders == 0:
                    # Use unique 24h traders as proxy for holders
                    holders = int(txns.get('h24', {}).get('unique', 0) or 0)

                return {
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                    'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                    'price': float(pair.get('priceUsd', 0) or 0),
                    'mcap': float(pair.get('marketCap', 0) or 0),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                    'volume_1h': float(pair.get('volume', {}).get('h1', 0) or 0),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                    'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0) or 0),
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                    'buys_1h': buys_1h,
                    'sells_1h': sells_1h,
                    'buys_24h': buys_24h,
                    'sells_24h': sells_24h,
                    'holders': holders,
                }

    except Exception as e:
        logger.debug(f"DexScreener error for {token_address[:8]}: {e}")
        return None


async def fetch_pumpportal(token_address: str) -> Optional[Dict]:
    """Fetch from PumpPortal (pre-grad tokens on pump.fun bonding curve)."""
    try:
        url = f"https://pumpportal.fun/api/data/token-info?ca={token_address}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()

                if not data or 'error' in data:
                    return None

                # Calculate price from bonding curve
                # Handle lamports vs SOL (V2 fix: values > 1000 are lamports)
                v_sol_raw = float(data.get('vSolInBondingCurve', 0) or 0)
                virtual_sol = v_sol_raw / 1e9 if v_sol_raw > 1000 else v_sol_raw

                v_tokens_raw = float(data.get('vTokensInBondingCurve', 0) or 0)
                virtual_tokens = v_tokens_raw / 1e6 if v_tokens_raw > 1e9 else v_tokens_raw  # 6 decimals

                if virtual_tokens > 0:
                    price_sol = virtual_sol / virtual_tokens
                else:
                    price_sol = 0

                # Get SOL price for USD conversion
                sol_price = await get_sol_price()
                price_usd = price_sol * sol_price

                # Calculate bonding curve percentage (85 SOL = graduation)
                bonding_pct = min((virtual_sol / 85) * 100, 100) if virtual_sol > 0 else 0

                # Estimate MCAP (virtual_sol * 2 is approximate fully diluted)
                mcap = virtual_sol * sol_price * 2

                # Estimate holders from bonding curve progress
                # More SOL in curve = more buyers. Rough estimate: 5-10 holders per SOL
                estimated_holders = max(10, int(virtual_sol * 7))

                return {
                    'symbol': data.get('symbol', 'UNKNOWN'),
                    'name': data.get('name', 'Unknown'),
                    'price': price_usd,
                    'mcap': mcap,
                    'liquidity': virtual_sol * sol_price,  # Bonding curve liquidity
                    'volume_1h': 0,  # PumpPortal doesn't provide this directly
                    'volume_24h': 0,
                    'price_change_1h': 0,
                    'price_change_24h': 0,
                    'buys_1h': 0,  # Not available from PumpPortal REST
                    'sells_1h': 0,
                    'buys_24h': 0,
                    'sells_24h': 0,
                    'holders': estimated_holders,
                    'bonding_pct': bonding_pct,
                    'virtual_sol': virtual_sol,
                }

    except Exception as e:
        logger.debug(f"PumpPortal error for {token_address[:8]}: {e}")
        return None


# SOL price cache
_sol_price_cache = {'price': 200.0, 'timestamp': 0}


async def get_sol_price() -> float:
    """Get current SOL price in USD (cached 5 min)."""
    import time

    now = time.time()
    if now - _sol_price_cache['timestamp'] < 300:  # 5 min cache
        return _sol_price_cache['price']

    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get('solana', {}).get('usd', 0)
                    if price > 0:
                        _sol_price_cache['price'] = price
                        _sol_price_cache['timestamp'] = now
                        return price

    except Exception as e:
        logger.debug(f"SOL price fetch error: {e}")

    return _sol_price_cache['price']
