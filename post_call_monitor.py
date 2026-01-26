"""
Post-Call Monitoring System (GROK RECOMMENDATION)
Monitors token price after signal to detect -15% drops in 5min and send exit alerts

Features:
- Track price changes for 5 minutes after signal
- Alert if price drops -15% or more
- Send Telegram exit alerts to warn users
- Log monitoring results for analysis
"""
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
import config


class PostCallMonitor:
    """
    Monitors tokens after signal is sent
    Alerts if price drops below exit threshold (-15% in 5min)
    """

    def __init__(self, dexscreener_fetcher=None, telegram_poster=None):
        self.dexscreener_fetcher = dexscreener_fetcher
        self.telegram_poster = telegram_poster
        self.monitoring_tasks = {}  # token_address -> asyncio.Task

    async def start_monitoring(
        self,
        token_address: str,
        signal_price: float,
        token_symbol: str,
        signal_score: int
    ):
        """
        Start monitoring a token after signal

        Args:
            token_address: Token mint address
            signal_price: Price when signal was sent
            token_symbol: Token symbol for alerts
            signal_score: Conviction score at signal time
        """
        if not config.TIMING_RULES['post_call_monitoring']['enabled']:
            return

        logger.info(f"   📊 Starting post-call monitoring: ${token_symbol} @ ${signal_price:.8f}")

        # Cancel existing monitoring for this token (if any)
        if token_address in self.monitoring_tasks:
            self.monitoring_tasks[token_address].cancel()

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_token(
                token_address,
                signal_price,
                token_symbol,
                signal_score
            )
        )
        self.monitoring_tasks[token_address] = task

    async def _monitor_token(
        self,
        token_address: str,
        signal_price: float,
        token_symbol: str,
        signal_score: int
    ):
        """
        Monitor token price for exit signals
        Runs for 5 minutes, checking every 30 seconds
        """
        try:
            monitoring_duration = config.TIMING_RULES['post_call_monitoring']['monitoring_duration']
            check_interval = config.TIMING_RULES['post_call_monitoring']['check_interval']
            exit_threshold = config.TIMING_RULES['post_call_monitoring']['exit_alert_threshold']

            start_time = datetime.utcnow()
            end_time = start_time + timedelta(seconds=monitoring_duration)
            checks_performed = 0
            exit_alert_sent = False

            logger.info(f"   🔍 Monitoring ${token_symbol} for {monitoring_duration}s (exit alert at {exit_threshold}%)")

            while datetime.utcnow() < end_time:
                await asyncio.sleep(check_interval)
                checks_performed += 1

                # Fetch current price
                if not self.dexscreener_fetcher:
                    logger.warning(f"   ⚠️  No DexScreener fetcher - cannot monitor price")
                    break

                try:
                    token_data = await self.dexscreener_fetcher.get_token_data(token_address)
                    if not token_data:
                        logger.debug(f"   ⚠️  No data for ${token_symbol} - check {checks_performed}")
                        continue

                    current_price = token_data.get('price', 0)
                    if current_price == 0:
                        continue

                    # Calculate price change %
                    price_change_pct = ((current_price - signal_price) / signal_price) * 100

                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    logger.debug(
                        f"   📊 ${token_symbol} check {checks_performed}: "
                        f"{price_change_pct:+.1f}% ({elapsed:.0f}s elapsed)"
                    )

                    # Check if exit threshold hit
                    if price_change_pct <= exit_threshold and not exit_alert_sent:
                        # EXIT ALERT!
                        logger.warning("\n" + "🚨" * 30)
                        logger.warning(f"   🚨 EXIT ALERT: ${token_symbol}")
                        logger.warning(f"   📉 Price dropped {price_change_pct:.1f}% in {elapsed:.0f}s")
                        logger.warning(f"   💵 Signal price: ${signal_price:.8f}")
                        logger.warning(f"   💵 Current price: ${current_price:.8f}")
                        logger.warning(f"   🎯 Score at signal: {signal_score}/100")
                        logger.warning("🚨" * 30 + "\n")

                        # Send Telegram alert
                        if (config.TIMING_RULES['post_call_monitoring']['send_telegram_alert'] and
                            self.telegram_poster and
                            config.ENABLE_TELEGRAM):
                            await self._send_exit_alert(
                                token_symbol,
                                token_address,
                                price_change_pct,
                                elapsed,
                                signal_price,
                                current_price
                            )

                        exit_alert_sent = True
                        # Continue monitoring but don't send duplicate alerts

                except Exception as e:
                    logger.error(f"   ❌ Error checking price for ${token_symbol}: {e}")
                    continue

            # Monitoring complete
            elapsed_total = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"   ✅ Monitoring complete for ${token_symbol} "
                f"({checks_performed} checks in {elapsed_total:.0f}s)"
            )

            # Cleanup
            if token_address in self.monitoring_tasks:
                del self.monitoring_tasks[token_address]

        except asyncio.CancelledError:
            logger.info(f"   🛑 Monitoring cancelled for ${token_symbol}")
        except Exception as e:
            logger.error(f"   ❌ Error monitoring ${token_symbol}: {e}")

    async def _send_exit_alert(
        self,
        token_symbol: str,
        token_address: str,
        price_change_pct: float,
        elapsed_seconds: float,
        signal_price: float,
        current_price: float
    ):
        """
        Send Telegram exit alert
        """
        try:
            message = f"""
🚨 **EXIT ALERT** 🚨

**Token:** ${token_symbol}
**Address:** `{token_address}`

📉 **Price dropped {price_change_pct:.1f}% in {elapsed_seconds/60:.1f} minutes**

💵 Signal price: ${signal_price:.8f}
💵 Current price: ${current_price:.8f}

⚠️ Consider taking profits or exiting position

[View on DexScreener](https://dexscreener.com/solana/{token_address})
"""

            await self.telegram_poster.send_message(message)
            logger.info(f"   ✅ Exit alert sent to Telegram for ${token_symbol}")

        except Exception as e:
            logger.error(f"   ❌ Error sending exit alert: {e}")

    def stop_monitoring(self, token_address: str):
        """
        Stop monitoring a specific token
        """
        if token_address in self.monitoring_tasks:
            self.monitoring_tasks[token_address].cancel()
            del self.monitoring_tasks[token_address]
            logger.info(f"   🛑 Stopped monitoring {token_address[:8]}...")

    def stop_all(self):
        """
        Stop all monitoring tasks
        """
        for task in self.monitoring_tasks.values():
            task.cancel()
        self.monitoring_tasks.clear()
        logger.info("   🛑 Stopped all post-call monitoring tasks")


# Singleton instance
_monitor_instance: Optional[PostCallMonitor] = None


def get_post_call_monitor(dexscreener_fetcher=None, telegram_poster=None) -> PostCallMonitor:
    """
    Get or create singleton PostCallMonitor instance
    """
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PostCallMonitor(
            dexscreener_fetcher=dexscreener_fetcher,
            telegram_poster=telegram_poster
        )
    return _monitor_instance
