"""
Performance Tracker - Monitor signal outcomes and post milestone updates
Dual tracking: pump.fun (pre-grad) + DexScreener (post-grad)
"""
import asyncio
import aiohttp
import json
import websockets
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger
from config import MILESTONES

class PerformanceTracker:
    """
    Tracks performance of posted signals
    - Uses PumpPortal WebSocket for pre-graduation tokens (40-60%)
    - Uses DexScreener API for post-graduation tokens (100%)
    - Detects milestone hits (2x, 5x, 10x, etc)
    - Posts updates to Telegram
    - Generates daily reports
    """
    
    def __init__(self, db, telegram_publisher):
        self.db = db
        self.telegram = telegram_publisher
        self.session = None
        self.running = False
        self.pumpportal_ws = None
        self.pumpportal_prices = {}  # {token_address: current_price} for pre-grad tokens
    
    async def start(self):
        """Start performance monitoring loop"""
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("📊 Performance tracker started")
        
        # Run monitoring loops
        asyncio.create_task(self._pumpportal_websocket_loop())
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._daily_report_loop())
    
    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.pumpportal_ws:
            await self.pumpportal_ws.close()
        if self.session:
            await self.session.close()
        logger.info("Performance tracker stopped")
    
    async def _pumpportal_websocket_loop(self):
        """Connect to PumpPortal WebSocket to track pre-graduation token prices"""
        while self.running:
            try:
                logger.info("🔌 Performance tracker connecting to PumpPortal...")
                
                async with websockets.connect(
                    'wss://pumpportal.fun/api/data',
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    self.pumpportal_ws = ws
                    logger.info("✅ Performance tracker connected to PumpPortal")
                    
                    # Subscribe to all token trades
                    await ws.send(json.dumps({
                        "method": "subscribeTokenTrade",
                        "keys": ["*"]
                    }))
                    
                    # Listen for price updates
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            # Get price updates for tokens we're tracking
                            if data.get('txType') in ['buy', 'sell']:
                                token_address = data.get('mint')
                                price_usd = data.get('priceUsd', 0)
                                
                                if token_address and price_usd:
                                    # Store current price
                                    self.pumpportal_prices[token_address] = float(price_usd)
                                    
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing PumpPortal message: {e}")
                            
            except Exception as e:
                logger.warning(f"⚠️ PumpPortal WebSocket error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
    
    async def _monitoring_loop(self):
        """Main monitoring loop - checks every minute"""
        while self.running:
            try:
                await self._check_all_signals()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _daily_report_loop(self):
        """Posts daily report at midnight UTC"""
        while self.running:
            try:
                # Calculate time until next midnight UTC
                now = datetime.utcnow()
                tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                seconds_until_midnight = (tomorrow - now).total_seconds()
                
                # Wait until midnight
                await asyncio.sleep(seconds_until_midnight)
                
                # Post daily report
                await self.post_daily_report()
                
            except Exception as e:
                logger.error(f"❌ Error in daily report loop: {e}")
                await asyncio.sleep(3600)  # Try again in an hour
    
    async def _check_all_signals(self):
        """Check performance of all active signals"""
        try:
            # Get all posted signals from today and yesterday (still relevant)
            signals = await self._get_active_signals()
            
            for signal in signals:
                await self._check_signal_performance(signal)
                
        except Exception as e:
            logger.error(f"❌ Error checking signals: {e}")
    
    async def _get_active_signals(self) -> List[Dict]:
        """Get signals that are still being tracked (posted in last 24 hours)"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT s.*, 
                       COALESCE(MAX(p.milestone), 0) as max_milestone_reached
                FROM signals s
                LEFT JOIN performance p ON s.token_address = p.token_address
                WHERE s.signal_posted = TRUE
                AND s.created_at > NOW() - INTERVAL '24 hours'
                GROUP BY s.id
                HAVING COALESCE(MAX(p.milestone), 0) < 100
                ORDER BY s.created_at DESC
            ''')
            return [dict(row) for row in rows]
    
    async def _check_signal_performance(self, signal: Dict):
        """Check current price and detect milestone hits"""
        try:
            token_address = signal['token_address']
            entry_price = signal['entry_price']
            signal_type = signal.get('signal_type', 'POST_GRADUATION')
            
            if not entry_price or entry_price == 0:
                return
            
            # Get current price based on signal type
            if signal_type == 'PRE_GRADUATION':
                # Token still on pump.fun - use PumpPortal
                current_price = await self._get_pumpfun_price(token_address)
                
                # If can't get pre-grad price, might have graduated
                if not current_price:
                    # Try DexScreener as fallback
                    current_price = await self._get_dexscreener_price(token_address)
                    if current_price:
                        # Token graduated! Update signal type
                        logger.info(f"🎓 {signal['token_symbol']} graduated - switching to DexScreener tracking")
                        await self._update_signal_type(token_address, 'POST_GRADUATION')
                        signal_type = 'POST_GRADUATION'
                
                if not current_price:
                    return
                    
                logger.debug(f"📊 Pre-grad tracking: {signal['token_symbol']} at ${current_price:.8f}")
                
            else:  # POST_GRADUATION
                # Token graduated to Raydium - use DexScreener
                current_price = await self._get_dexscreener_price(token_address)
                
                if not current_price:
                    return
                    
                logger.debug(f"📊 Post-grad tracking: {signal['token_symbol']} at ${current_price:.8f}")
            
            # Update current price in database
            await self.db.update_price(token_address, current_price)
            
            # Calculate current multiple
            multiple = current_price / entry_price
            
            # Check for milestone hits
            max_milestone_reached = signal.get('max_milestone_reached', 0)
            
            for milestone in MILESTONES:
                if multiple >= milestone and milestone > max_milestone_reached:
                    # New milestone reached!
                    logger.info(f"🎯 {signal['token_symbol']} hit {milestone}x milestone!")
                    
                    # Save to database
                    await self.db.insert_milestone(token_address, milestone, current_price)
                    
                    # Post update to Telegram
                    await self._post_milestone_update(signal, milestone, current_price, multiple, signal_type)
                    
        except Exception as e:
            logger.error(f"❌ Error checking performance for {signal.get('token_symbol')}: {e}")
    
    async def _get_dexscreener_price(self, token_address: str) -> float:
        """Get current price from DexScreener (for post-graduation tokens)"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    pairs = data.get('pairs', [])
                    if pairs:
                        # Get the most liquid pair
                        pair = pairs[0]
                        price = float(pair.get('priceUsd', 0))
                        return price
                    
        except Exception as e:
            logger.debug(f"Error fetching DexScreener price for {token_address[:8]}: {e}")
        
        return None
    
    async def _get_pumpfun_price(self, token_address: str) -> float:
        """
        Get current price for pre-graduation token
        First checks PumpPortal WebSocket cache, then falls back to API
        """
        # Try WebSocket cache first (fastest)
        if token_address in self.pumpportal_prices:
            return self.pumpportal_prices[token_address]
        
        # Fallback: query PumpPortal API directly
        try:
            # PumpPortal has endpoints for token data
            url = f"https://pumpportal.fun/api/data/token/{token_address}"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get('priceUsd', 0)
                    if price:
                        return float(price)
        except Exception as e:
            logger.debug(f"Error fetching pump.fun price for {token_address[:8]}: {e}")
        
        return None
    
    async def _update_signal_type(self, token_address: str, new_type: str):
        """Update signal type when token graduates"""
        async with self.db.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals
                SET signal_type = $1
                WHERE token_address = $2
            ''', new_type, token_address)
    
    async def _post_milestone_update(self, signal: Dict, milestone: float, current_price: float, multiple: float, signal_type: str):
        """Post milestone update to Telegram"""
        try:
            symbol = signal['token_symbol']
            token_address = signal['token_address']
            entry_price = signal['entry_price']
            
            # Calculate time since signal
            time_since = datetime.utcnow() - signal['created_at']
            hours = int(time_since.total_seconds() / 3600)
            minutes = int((time_since.total_seconds() % 3600) / 60)
            
            # Determine emoji based on milestone
            if milestone >= 10:
                emoji = "🚀🚀🚀"
            elif milestone >= 5:
                emoji = "🚀🚀"
            else:
                emoji = "🚀"
            
            # Tracking source for transparency
            price_source = "pump.fun (PumpPortal)" if signal_type == 'PRE_GRADUATION' else "Raydium (DexScreener)"
            
            # Build message
            message = f"""🎯 <b>MILESTONE REACHED</b> {emoji}

<b>${symbol}</b> hit <b>{milestone}x</b>!

📊 Signal Type: {signal_type.replace('_', ' ').title()}
💰 Entry: ${entry_price:.8f}
💎 Current: ${current_price:.8f}
📈 Gain: <b>+{(multiple - 1) * 100:.1f}%</b> ({milestone}x)
⏱ Time: {hours}h {minutes}m
📡 Source: {price_source}

🔗 <a href="https://dexscreener.com/solana/{token_address}">Chart</a> | <a href="https://pump.fun/{token_address}">Pump.fun</a>

<code>{token_address}</code>
"""
            
            await self.telegram.bot.send_message(
                chat_id=self.telegram.channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info(f"📤 Milestone update posted: {symbol} hit {milestone}x")
            
        except Exception as e:
            logger.error(f"❌ Failed to post milestone update: {e}")
    
    async def post_daily_report(self):
        """Post daily performance report"""
        try:
            logger.info("📊 Generating daily report...")
            
            # Get today's signals
            signals = await self.db.get_signals_today()
            
            if not signals:
                logger.info("No signals posted today, skipping daily report")
                return
            
            # Calculate stats
            total_signals = len(signals)
            
            # Get performance for each signal
            signal_performance = []
            for signal in signals:
                current_price = signal.get('current_price')
                entry_price = signal.get('entry_price')
                
                if current_price and entry_price and entry_price > 0:
                    multiple = current_price / entry_price
                    gain_pct = (multiple - 1) * 100
                    
                    signal_performance.append({
                        'symbol': signal['token_symbol'],
                        'signal_type': signal['signal_type'],
                        'multiple': multiple,
                        'gain_pct': gain_pct,
                        'conviction': signal['conviction_score']
                    })
            
            # Sort by gain
            signal_performance.sort(key=lambda x: x['gain_pct'], reverse=True)
            
            # Calculate win rate (anything >0% is a win)
            winners = [s for s in signal_performance if s['gain_pct'] > 0]
            win_rate = (len(winners) / len(signal_performance) * 100) if signal_performance else 0
            
            # Calculate average gain
            avg_gain = sum(s['gain_pct'] for s in signal_performance) / len(signal_performance) if signal_performance else 0
            
            # Get top 10
            top_10 = signal_performance[:10]
            
            # Build message
            message = f"""📊 <b>DAILY PERFORMANCE REPORT</b>

📅 {datetime.utcnow().strftime('%B %d, %Y')}

📈 <b>Overview:</b>
🔔 Total Signals: {total_signals}
✅ Winners: {len(winners)}
❌ Losers: {len(signal_performance) - len(winners)}
📊 Win Rate: <b>{win_rate:.1f}%</b>
💰 Avg Gain: <b>{avg_gain:+.1f}%</b>

🏆 <b>TOP 10 PERFORMERS:</b>
"""
            
            for i, perf in enumerate(top_10, 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                signal_emoji = "⚡" if perf['signal_type'] == 'PRE_GRADUATION' else "🎓"
                
                message += f"\n{emoji} ${perf['symbol']} {signal_emoji}\n"
                message += f"   Gain: <b>{perf['gain_pct']:+.1f}%</b> ({perf['multiple']:.2f}x)\n"
                message += f"   Conviction: {perf['conviction']}/100\n"
            
            message += "\n⚡ = Pre-graduation signal (40-60%)\n"
            message += "🎓 = Post-graduation signal (100%)\n\n"
            message += "⚠️ <i>Past performance ≠ future results</i>"
            
            await self.telegram.bot.send_message(
                chat_id=self.telegram.channel_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info("✅ Daily report posted")
            
        except Exception as e:
            logger.error(f"❌ Failed to post daily report: {e}")
    
    async def get_stats(self) -> Dict:
        """Get current performance stats (for admin commands)"""
        try:
            # Get today's signals
            signals = await self.db.get_signals_today()
            
            # Calculate quick stats
            total = len(signals)
            
            signal_performance = []
            for signal in signals:
                current_price = signal.get('current_price')
                entry_price = signal.get('entry_price')
                
                if current_price and entry_price and entry_price > 0:
                    gain_pct = ((current_price / entry_price) - 1) * 100
                    signal_performance.append(gain_pct)
            
            winners = len([g for g in signal_performance if g > 0])
            win_rate = (winners / len(signal_performance) * 100) if signal_performance else 0
            avg_gain = sum(signal_performance) / len(signal_performance) if signal_performance else 0
            
            return {
                'total_signals': total,
                'winners': winners,
                'losers': len(signal_performance) - winners,
                'win_rate': win_rate,
                'avg_gain': avg_gain
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
