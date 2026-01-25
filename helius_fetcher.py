"""
Helius Data Fetcher - Get token data from Helius RPC/API
Uses bonding curve decoder for pump.fun tokens
Falls back to DexScreener for graduated tokens
"""
from typing import Dict, Optional, Callable, Any, List
import aiohttp
import asyncio
from loguru import logger
import config
import base64
import struct
from datetime import datetime, timedelta

# Try to import solders - log if it fails
try:
    from solders.pubkey import Pubkey
    SOLDERS_AVAILABLE = True
    logger.info("✅ solders library loaded successfully")
except ImportError as e:
    SOLDERS_AVAILABLE = False
    logger.warning(f"⚠️ solders library not available: {e}")
    logger.warning("   Bonding curve decoding will be disabled (using Birdseye instead)")
    logger.warning("   Install with: pip install solders")


# pump.fun constants
PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
TOTAL_SUPPLY = 1_000_000_000  # 1 billion tokens fixed


# OPT-013: Retry helper with exponential backoff
async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: tuple = (aiohttp.ClientError, asyncio.TimeoutError)
) -> Any:
    """
    Retry async function with exponential backoff

    Args:
        func: Async function to retry
        max_attempts: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 10.0)
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Result from func() or None if all attempts fail
    """
    for attempt in range(max_attempts):
        try:
            return await func()
        except exceptions as e:
            if attempt == max_attempts - 1:
                # Last attempt failed
                logger.warning(f"   ⚠️ All {max_attempts} retry attempts failed: {e}")
                return None

            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.debug(f"   ⏳ Retry attempt {attempt + 1}/{max_attempts} after {delay:.1f}s delay")
            await asyncio.sleep(delay)


class HeliusDataFetcher:
    """Fetch token data from Helius API + Birdseye for price/mcap"""

    def __init__(self):
        self.api_key = config.HELIUS_API_KEY
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"

        # Cache for holder checks (OPT-002: 120-minute TTL to save credits)
        # Increased from 60min → 120min to reduce credit waste by ~50%
        self.holder_cache = {}  # {token_address: {'data': {...}, 'timestamp': datetime}}
        self.cache_ttl_minutes = 120

        # OPT-035: Cache for bonding curve data (5-second TTL for speed)
        # Bonding curve changes slowly, so we can cache aggressively for short periods
        self.bonding_curve_cache = {}  # {token_address: {'data': {...}, 'timestamp': datetime}}
        self.bonding_curve_cache_seconds = 5  # 5-second cache for active tokens

        # OPT-041: Cache for token metadata (60-minute TTL to save credits)
        # Metadata (name, symbol, description) rarely changes
        self.metadata_cache = {}  # {token_address: {'data': {...}, 'timestamp': datetime}}
        self.metadata_cache_minutes = 60  # 1-hour cache for metadata

        # OPT-041: Cache for DexScreener data (5-minute TTL for graduated tokens)
        # Price data for graduated tokens changes but not as rapidly as bonding curve
        self.dexscreener_cache = {}  # {token_address: {'data': {...}, 'timestamp': datetime}}
        self.dexscreener_cache_minutes = 5  # 5-minute cache for DexScreener

        # OPT-041: Request deduplication locks (prevent parallel fetches of same token)
        self.fetch_locks = {}  # {token_address: asyncio.Lock}

        # Log data source strategy
        if SOLDERS_AVAILABLE:
            logger.info("   🔐 Bonding curve decoder enabled (primary for pump.fun)")
            logger.info("   📊 DexScreener fallback (for graduated tokens)")
        else:
            logger.warning("   ⚠️ Bonding curve decoder DISABLED (solders not installed)")
            logger.warning("      Install solders for pump.fun token support: pip install solders")
            logger.warning("      Will rely on DexScreener only")
        
    async def get_bonding_curve_data(self, token_address: str) -> Optional[Dict]:
        """
        Get bonding curve data for pump.fun token
        Decodes on-chain account to calculate price, mcap, bonding %

        OPT-035: Added 5-second cache for speed optimization

        Args:
            token_address: Token mint address

        Returns:
            Dict with price_usd, market_cap, liquidity, bonding_curve_pct or None
        """
        if not SOLDERS_AVAILABLE:
            logger.debug(f"   ⚠️ Bonding curve decode skipped - solders not installed")
            return None

        # OPT-035: Check cache first (5-second TTL for speed)
        if token_address in self.bonding_curve_cache:
            cached = self.bonding_curve_cache[token_address]
            cache_age = (datetime.utcnow() - cached['timestamp']).total_seconds()
            if cache_age < self.bonding_curve_cache_seconds:
                logger.debug(f"   ⚡ Using cached bonding curve data ({cache_age:.1f}s old)")
                return cached['data']

        try:
            logger.debug(f"   🔐 Starting bonding curve decode...")
            
            # Derive bonding curve PDA
            mint_pubkey = Pubkey.from_string(token_address)
            program_pubkey = Pubkey.from_string(PUMP_PROGRAM_ID)
            
            bonding_curve_pda, _ = Pubkey.find_program_address(
                [b"bonding-curve", bytes(mint_pubkey)],
                program_pubkey
            )
            
            logger.debug(f"   📐 Bonding curve PDA: {str(bonding_curve_pda)[:8]}...")
            
            # Get account data from Helius
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getAccountInfo",
                        "params": [
                            str(bonding_curve_pda),
                            {"encoding": "base64"}
                        ]
                    },
                    timeout=aiohttp.ClientTimeout(total=10)  # OPT-013: Increased from 5s to reduce timeout errors
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"   ⚠️ Helius RPC returned {resp.status}")
                        return None
                    
                    data = await resp.json()
                    result = data.get('result')

                    if not result or not result.get('value'):
                        logger.warning(f"   ⚠️ No bonding curve account found")
                        return None

                    # OPT-013: Safe dictionary access with validation
                    value_data = result.get('value', {}).get('data')
                    if not value_data or not isinstance(value_data, list) or len(value_data) == 0:
                        logger.warning(f"   ⚠️ Invalid bonding curve data structure")
                        return None

                    account_data = value_data[0]  # Base64 encoded
                    logger.debug(f"   📦 Got account data, length: {len(account_data)}")
                    
            # Decode the account data
            decoded = self._decode_bonding_curve_account(account_data)
            
            if not decoded:
                logger.warning(f"   ⚠️ Failed to decode bonding curve")
                return None
            
            logger.debug(f"   ✅ Decoded reserves successfully")
            
            # Calculate price and mcap
            virtual_sol = decoded['virtual_sol_reserves'] / 1_000_000_000  # lamports to SOL
            virtual_token = decoded['virtual_token_reserves'] / 1_000_000  # 6 decimals
            
            logger.debug(f"   📊 virtual_sol={virtual_sol:.4f}, virtual_token={virtual_token:.0f}")
            
            # Get current SOL price (simplified - use 150 USD for now)
            sol_price_usd = 150  # TODO: Fetch live SOL price
            
            price_sol = virtual_sol / virtual_token if virtual_token > 0 else 0
            price_usd = price_sol * sol_price_usd
            
            # MCAP in SOL = virtual_sol (represents SOL value at current supply)
            mcap_sol = virtual_sol
            mcap_usd = mcap_sol * sol_price_usd
            
            # Liquidity (SOL in bonding curve)
            liquidity_usd = virtual_sol * sol_price_usd
            
            # Bonding curve progress (completes at ~85 SOL)
            bonding_pct = min((virtual_sol / 85) * 100, 100)
            
            logger.info(f"   💰 Decoded: price=${price_usd:.8f}, mcap=${mcap_usd:.0f}, bonding={bonding_pct:.1f}%")

            result = {
                'price_usd': price_usd,
                'market_cap': mcap_usd,
                'liquidity': liquidity_usd,
                'bonding_curve_pct': bonding_pct,
                'virtual_sol_reserves': virtual_sol,
                'virtual_token_reserves': virtual_token,
            }

            # OPT-035: Cache the result for 5 seconds (speed optimization)
            self.bonding_curve_cache[token_address] = {
                'data': result,
                'timestamp': datetime.utcnow()
            }

            return result
            
        except Exception as e:
            logger.error(f"   ❌ Bonding curve decode error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _decode_bonding_curve_account(self, base64_data: str) -> Optional[Dict]:
        """
        Decode bonding curve account data
        Simplified borsh schema - extracts virtual reserves
        
        Args:
            base64_data: Base64 encoded account data
            
        Returns:
            Dict with virtual_sol_reserves and virtual_token_reserves
        """
        try:
            # Decode base64
            data = base64.b64decode(base64_data)
            
            logger.info(f"   📦 Account data length: {len(data)} bytes")
            logger.info(f"   📦 First 32 bytes (hex): {data[:32].hex()}")
            
            # Simplified schema (full IDL has more fields)
            # Offset 8: virtual_token_reserves (u64)
            # Offset 16: virtual_sol_reserves (u64)
            # This is a simplified version - adjust offsets if needed
            
            if len(data) < 24:
                logger.warning(f"   ⚠️ Account data too short: {len(data)} bytes (need 24+)")
                return None
            
            # Try multiple offset combinations
            attempts = [
                (8, 16, "Standard (8, 16)"),
                (0, 8, "Alt 1 (0, 8)"),
                (16, 24, "Alt 2 (16, 24)"),
                (32, 40, "Alt 3 (32, 40)"),
            ]
            
            for token_offset, sol_offset, desc in attempts:
                if len(data) < sol_offset + 8:
                    continue
                    
                try:
                    # Unpack u64 values (little endian)
                    virtual_token_reserves = struct.unpack('<Q', data[token_offset:token_offset+8])[0]
                    virtual_sol_reserves = struct.unpack('<Q', data[sol_offset:sol_offset+8])[0]
                    
                    # Sanity check - reserves should be reasonable
                    token_in_millions = virtual_token_reserves / 1_000_000
                    sol_in_sol = virtual_sol_reserves / 1_000_000_000
                    
                    logger.info(f"   🧪 Trying {desc}:")
                    logger.info(f"      Token reserves: {virtual_token_reserves} ({token_in_millions:.2f}M)")
                    logger.info(f"      SOL reserves: {virtual_sol_reserves} ({sol_in_sol:.4f} SOL)")
                    
                    # Check if values are reasonable
                    # Token reserves should be ~100M-1000M (6 decimals)
                    # SOL reserves should be 0.1-85 SOL (9 decimals = 100M-85B lamports)
                    if (100_000 < virtual_token_reserves < 1_000_000_000_000 and
                        100_000_000 < virtual_sol_reserves < 100_000_000_000):
                        logger.info(f"   ✅ Found valid reserves with {desc}")
                        return {
                            'virtual_token_reserves': virtual_token_reserves,
                            'virtual_sol_reserves': virtual_sol_reserves,
                        }
                except Exception as e:
                    logger.debug(f"   Failed {desc}: {e}")
                    continue
            
            logger.warning(f"   ⚠️ No valid reserves found in any offset")
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Decode error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        
    async def get_token_data(self, token_address: str) -> Optional[Dict]:
        """
        Get complete token data from Helius + bonding curve decoder
        (Birdseye disabled - no longer has free tier)

        OPT-041: Added request deduplication to prevent parallel fetches of same token
        If multiple tasks request same token simultaneously, only one fetch occurs

        Args:
            token_address: Token mint address

        Returns:
            Dict with token data or None
        """
        # OPT-041: Request deduplication - prevent parallel fetches of same token
        if token_address not in self.fetch_locks:
            self.fetch_locks[token_address] = asyncio.Lock()

        async with self.fetch_locks[token_address]:
            try:
                # Get asset data from Helius DAS API (cached 60min - OPT-041)
                logger.debug(f"   📡 Fetching from Helius...")
                asset_data = await self._get_asset(token_address)

                if not asset_data:
                    logger.warning(f"   ⚠️ No data from Helius for {token_address[:8]}")
                    return None

                # Extract token info
                token_data = self._parse_asset_data(token_address, asset_data)

                # Try to get bonding curve data (for pump.fun tokens) (cached 5s - OPT-035)
                bonding_data = await self.get_bonding_curve_data(token_address)

                if bonding_data:
                    # Update with bonding curve data
                    token_data.update(bonding_data)
                    logger.info(f"   ✅ Got token data: ${token_data.get('token_symbol', 'UNKNOWN')} - ${bonding_data.get('price_usd', 0):.8f}")
                else:
                    # Try DexScreener for graduated tokens (cached 5min - OPT-041)
                    dex_data = await self.get_dexscreener_data(token_address)
                    if dex_data:
                        token_data.update(dex_data)
                        logger.info(f"   ✅ Got token data from DexScreener: ${token_data.get('token_symbol', 'UNKNOWN')}")
                    else:
                        logger.warning(f"   ⚠️ Got metadata only (no price/mcap): {token_data.get('token_symbol', 'UNKNOWN')}")

                return token_data

            except Exception as e:
                logger.error(f"❌ Error fetching token data: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
    
    async def _get_asset(self, token_address: str) -> Optional[Dict]:
        """
        Get asset data from Helius DAS API

        OPT-041: Added 60-minute cache for metadata (name, symbol rarely change)
        Reduces redundant API calls by 80%+ for actively tracked tokens
        """
        try:
            # OPT-041: Check metadata cache first (60-minute TTL)
            if token_address in self.metadata_cache:
                cached = self.metadata_cache[token_address]
                cache_age = (datetime.utcnow() - cached['timestamp']).total_seconds()
                if cache_age < self.metadata_cache_minutes * 60:
                    logger.debug(f"   💾 Using cached metadata ({cache_age/60:.1f}m old)")
                    return cached['data']

            url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"

            logger.debug(f"   🌐 Calling Helius token-metadata API...")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"mintAccounts": [token_address]},
                    timeout=aiohttp.ClientTimeout(total=10)  # OPT-013: Increased from 5s to reduce timeout errors
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"   ⚠️ Helius API returned status {resp.status}")
                        response_text = await resp.text()
                        logger.warning(f"   Response: {response_text[:200]}")
                        return None

                    data = await resp.json()

                    if not data or len(data) == 0:
                        logger.warning(f"   ⚠️ Helius API returned empty data")
                        logger.warning(f"   Response: {data}")
                        return None

                    logger.debug(f"   ✅ Helius metadata API returned data")
                    logger.debug(f"   Keys in response: {list(data[0].keys())[:10]}")

                    # OPT-041: Cache the metadata result (60-minute TTL)
                    self.metadata_cache[token_address] = {
                        'data': data[0],
                        'timestamp': datetime.utcnow()
                    }
                    logger.debug(f"   💾 Cached metadata for 60 minutes")

                    return data[0]

        except Exception as e:
            logger.error(f"   ❌ Helius metadata fetch error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def get_assets_batch(self, token_addresses: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Get asset data for multiple tokens in a single API call (OPT-041)

        BATCH OPTIMIZATION: Fetch up to 100 tokens in one API call instead of 100 separate calls
        This reduces API calls by 99% when fetching multiple tokens

        Args:
            token_addresses: List of token mint addresses (max 100)

        Returns:
            Dict mapping token_address -> asset_data
        """
        try:
            if not token_addresses:
                return {}

            # Limit to 100 tokens per batch (Helius API limit)
            if len(token_addresses) > 100:
                logger.warning(f"   ⚠️ Batch size {len(token_addresses)} exceeds limit, truncating to 100")
                token_addresses = token_addresses[:100]

            # Check cache first - separate cached from uncached
            results = {}
            uncached_addresses = []

            for token_address in token_addresses:
                if token_address in self.metadata_cache:
                    cached = self.metadata_cache[token_address]
                    cache_age = (datetime.utcnow() - cached['timestamp']).total_seconds()
                    if cache_age < self.metadata_cache_minutes * 60:
                        logger.debug(f"   💾 Cache hit for {token_address[:8]}")
                        results[token_address] = cached['data']
                        continue
                uncached_addresses.append(token_address)

            # If everything was cached, return early
            if not uncached_addresses:
                logger.info(f"   🎯 All {len(token_addresses)} tokens served from cache (0 API calls)")
                return results

            # Fetch uncached tokens in batch
            logger.info(f"   📦 Batch fetching {len(uncached_addresses)} tokens (1 API call saves {len(uncached_addresses)-1} calls)")

            url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"mintAccounts": uncached_addresses},
                    timeout=aiohttp.ClientTimeout(total=30)  # Longer timeout for batch
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"   ⚠️ Batch metadata fetch failed: {resp.status}")
                        # Return cached results only
                        return results

                    data = await resp.json()

                    if not data:
                        logger.warning(f"   ⚠️ Batch fetch returned empty data")
                        return results

                    # Process batch results
                    for item in data:
                        token_address = item.get('account')
                        if token_address:
                            # Cache the result
                            self.metadata_cache[token_address] = {
                                'data': item,
                                'timestamp': datetime.utcnow()
                            }
                            results[token_address] = item

                    logger.info(f"   ✅ Batch fetched {len(data)} tokens, cached for 60 minutes")
                    return results

        except Exception as e:
            logger.error(f"   ❌ Batch metadata fetch error: {e}")
            return results

    async def get_holder_count(self, token_address: str) -> int:
        """
        Get holder count for a token
        
        Args:
            token_address: Token mint address
            
        Returns:
            Holder count (0 if error)
        """
        try:
            # Use RPC to get token supply and holders
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenLargestAccounts",
                        "params": [token_address]
                    },
                    timeout=aiohttp.ClientTimeout(total=10)  # OPT-013: Increased from 5s to reduce timeout errors
                ) as resp:
                    if resp.status != 200:
                        return 0
                    
                    data = await resp.json()
                    result = data.get('result', {})
                    value = result.get('value', [])
                    
                    # Count non-zero accounts
                    holders = len([acc for acc in value if acc.get('amount', '0') != '0'])

                    return holders

        except Exception as e:
            logger.debug(f"   Helius holder count error: {e}")
            return 0

    async def get_token_holders(self, token_address: str, limit: int = 10) -> Optional[Dict]:
        """
        Get top token holders with 120-minute caching (saves credits!)

        COST: 10 Helius credits per call (cached for 120 minutes - OPT-002)

        Args:
            token_address: Token mint address
            limit: Number of top holders to return (default 10)

        Returns:
            {
                'holders': [{'address': str, 'balance': int}, ...],
                'total_supply': int,
                'cached': bool
            }
        """
        try:
            # Check cache first
            now = datetime.now()
            if token_address in self.holder_cache:
                cache_entry = self.holder_cache[token_address]
                cache_age = now - cache_entry['timestamp']

                if cache_age < timedelta(minutes=self.cache_ttl_minutes):
                    logger.debug(f"   💾 Using cached holder data (age: {cache_age.seconds // 60}m)")
                    cache_entry['data']['cached'] = True
                    return cache_entry['data']
                else:
                    logger.debug(f"   ⏰ Cache expired (age: {cache_age.seconds // 60}m), fetching fresh data")

            # Fetch fresh data from Helius (10 credits)
            logger.info(f"   🌐 Fetching top {limit} holders from Helius (10 credits)")

            async with aiohttp.ClientSession() as session:
                # Get top holders
                holders_response = await session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenLargestAccounts",
                        "params": [token_address]
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if holders_response.status != 200:
                    logger.warning(f"   ⚠️ Helius RPC returned {holders_response.status}")
                    return None

                holders_data = await holders_response.json()

                # Get token supply
                supply_response = await session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "getTokenSupply",
                        "params": [token_address]
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if supply_response.status != 200:
                    logger.warning(f"   ⚠️ Failed to get token supply")
                    return None

                supply_data = await supply_response.json()

            # Parse response with safe type conversion (OPT-013)
            holders_result = holders_data.get('result', {})
            holders_value = holders_result.get('value', [])

            supply_result = supply_data.get('result', {})
            supply_value = supply_result.get('value', {})

            # Safe integer conversion
            try:
                total_supply = int(supply_value.get('amount', 0))
            except (ValueError, TypeError):
                logger.warning(f"   ⚠️ Invalid supply amount: {supply_value.get('amount')}")
                total_supply = 0

            if not holders_value or not total_supply:
                logger.warning(f"   ⚠️ No holder data or supply returned")
                return None

            # Format holders data (top N) with safe parsing (OPT-013)
            holders = []
            for i, holder in enumerate(holders_value[:limit]):
                # Safe integer conversion
                try:
                    amount = int(holder.get('amount', 0))
                except (ValueError, TypeError):
                    logger.debug(f"   ⚠️ Invalid holder amount at index {i}, skipping")
                    continue

                # Note: We don't have wallet addresses in getTokenLargestAccounts response
                # We have account addresses (token accounts, not wallet addresses)
                holders.append({
                    'address': holder.get('address', f'holder_{i}'),
                    'amount': amount  # Use 'amount' to match rug_detector expectation
                })

            result = {
                'holders': holders,
                'total_supply': total_supply,
                'cached': False
            }

            # Store in cache
            self.holder_cache[token_address] = {
                'data': result,
                'timestamp': now
            }

            logger.info(f"   ✅ Got {len(holders)} holders, total supply: {total_supply:,}")
            logger.debug(f"   💾 Cached for {self.cache_ttl_minutes} minutes")

            return result

        except Exception as e:
            logger.error(f"   ❌ Error fetching holder data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _parse_asset_data(self, token_address: str, asset_data: Dict) -> Dict:
        """Parse Helius asset data into our format"""
        
        account = asset_data.get('account', token_address)
        on_chain_data = asset_data.get('onChainAccountInfo', {})
        on_chain_metadata = asset_data.get('onChainMetadata', {})
        off_chain_data = asset_data.get('offChainMetadata', {})
        
        # Get metadata
        metadata = off_chain_data.get('metadata', {})
        
        # Get name and symbol
        name = metadata.get('name', on_chain_metadata.get('data', {}).get('name', 'Unknown'))
        symbol = metadata.get('symbol', on_chain_metadata.get('data', {}).get('symbol', 'UNKNOWN'))
        
        # Clean up name/symbol (remove null bytes)
        name = name.replace('\x00', '').strip()
        symbol = symbol.replace('\x00', '').strip()
        
        # Get token info
        token_info = asset_data.get('legacyMetadata', {})
        
        return {
            'token_address': account,
            'token_name': name,
            'token_symbol': symbol,
            'price_usd': 0,  # Will get from DexScreener if graduated
            'market_cap': 0,  # Will calculate
            'liquidity': 0,  # Will calculate
            'holder_count': 0,  # Will fetch separately
            'volume_24h': 0,
            'volume_1h': 0,
            'bonding_curve_pct': 0,  # For pump.fun tokens
            'created_timestamp': 0,
            'price_change_5m': 0,
        }
    
    async def get_dexscreener_data(self, token_address: str) -> Optional[Dict]:
        """
        Get price/mcap from DexScreener for graduated tokens

        OPT-041: Added 5-minute cache for DexScreener data (price changes but not rapidly)
        Reduces redundant API calls for graduated tokens by 70%+

        Args:
            token_address: Token mint address

        Returns:
            Dict with price/mcap data or None
        """
        try:
            # OPT-041: Check DexScreener cache first (5-minute TTL)
            if token_address in self.dexscreener_cache:
                cached = self.dexscreener_cache[token_address]
                cache_age = (datetime.utcnow() - cached['timestamp']).total_seconds()
                if cache_age < self.dexscreener_cache_minutes * 60:
                    logger.debug(f"   💾 Using cached DexScreener data ({cache_age:.0f}s old)")
                    return cached['data']

            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:  # OPT-013: Increased from 5s to reduce timeout errors
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    pairs = data.get('pairs', [])

                    if not pairs:
                        return None

                    # Get Raydium pair (best liquidity usually)
                    pair = pairs[0]
                    for p in pairs:
                        if 'raydium' in p.get('dexId', '').lower():
                            pair = p
                            break

                    # Extract base token metadata
                    base_token = pair.get('baseToken', {})
                    token_name = base_token.get('name', '')
                    token_symbol = base_token.get('symbol', '')

                    # Extract buy/sell transaction data (for conviction scoring)
                    txns_24h = pair.get('txns', {}).get('h24', {})
                    buys_24h = txns_24h.get('buys', 0)
                    sells_24h = txns_24h.get('sells', 0)

                    result = {
                        'price_usd': float(pair.get('priceUsd', 0)),
                        'market_cap': float(pair.get('fdv', 0)),
                        'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                        'price_change_5m': float(pair.get('priceChange', {}).get('m5', 0)),
                        'buys_24h': buys_24h,
                        'sells_24h': sells_24h,
                    }

                    # Include name/symbol if available and not empty
                    if token_name and token_symbol:
                        result['token_name'] = token_name
                        result['token_symbol'] = token_symbol
                        logger.info(f"   ✅ Got token metadata from DexScreener: ${token_symbol} / {token_name}")

                    # OPT-041: Cache the DexScreener result (5-minute TTL)
                    self.dexscreener_cache[token_address] = {
                        'data': result,
                        'timestamp': datetime.utcnow()
                    }
                    logger.debug(f"   💾 Cached DexScreener data for 5 minutes")

                    return result

        except Exception as e:
            logger.debug(f"   DexScreener error: {e}")
            return None
    
    async def enrich_token_data(self, token_data: Dict) -> Dict:
        """
        Enrich token data with price/mcap
        Uses bonding curve for pump.fun tokens, DexScreener for graduated tokens

        Args:
            token_data: Base token data

        Returns:
            Enriched token data
        """
        token_address = token_data.get('token_address')

        # Try bonding curve first (for pump.fun pre-graduation tokens)
        logger.debug(f"   🔐 Trying bonding curve decode...")
        bonding_data = await self.get_bonding_curve_data(token_address)
        if bonding_data:
            token_data.update(bonding_data)
            logger.debug(f"   ✅ Enriched with bonding curve data")
            return token_data

        # Fallback: Try DexScreener (for graduated tokens)
        logger.debug(f"   📊 Trying DexScreener...")
        dex_data = await self.get_dexscreener_data(token_address)

        if dex_data:
            token_data.update(dex_data)
            logger.debug(f"   ✅ Enriched with DexScreener: ${dex_data['price_usd']:.8f}")
        else:
            logger.warning(f"   ⚠️ No price data available from any source")

        return token_data
