"""
Post-Call Monitoring System (GROK RECOMMENDATION)
Monitors token price AND buyer velocity after signal to detect fades

Features:
- Track price changes for 10 minutes after signal
- Alert if price drops -15% or more (EXIT ALERT)
- Alert if buyer velocity fades (<5 new buyers in 2 min) (FADE ALERT)
- Send Telegram alerts to warn users
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
    Detects price fades (-15%) and buyer velocity fades (<5 buyers/2min)
    """

    def __init__(self, dexscreener_fetcher=None, telegram_poster=None, pump_monitor=None):
        self.dexscreener_fetcher = dexscreener_fetcher
        self.telegram_poster = telegram_poster
        self.pump_monitor = pump_monitor  # For buyer velocity tracking
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

        # Snapshot buyer count at signal time for fade detection
        signal_buyer_count = 0
        if self.pump_monitor:
            signal_buyer_count = len(self.pump_monitor.unique_buyers.get(token_address, set()))

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_token(
                token_address,
                signal_price,
                token_symbol,
                signal_score,
                signal_buyer_count
            )
        )
        self.monitoring_tasks[token_address] = task

    async def _monitor_token(
        self,
        token_address: str,
        signal_price: float,
        token_symbol: str,
        signal_score: int,
        signal_buyer_count: int = 0
    ):
        """
        Monitor token price and buyer velocity for fade signals
        Runs for 10 minutes, checking every 30 seconds
        """
        try:
            mon_cfg = config.TIMING_RULES['post_call_monitoring']
            monitoring_duration = mon_cfg['monitoring_duration']
            check_interval = mon_cfg['check_interval']
            exit_threshold = mon_cfg['exit_alert_threshold']

            # Buyer fade config
            buyer_fade_enabled = mon_cfg.get('buyer_fade_enabled', False)
            buyer_fade_threshold = mon_cfg.get('buyer_fade_threshold', 5)
            buyer_fade_window = mon_cfg.get('buyer_fade_window_seconds', 120)

            start_time = datetime.utcnow()
            end_time = start_time + timedelta(seconds=monitoring_duration)
            checks_performed = 0
            exit_alert_sent = False
            fade_alert_sent = False
            last_buyer_snapshot = signal_buyer_count
            last_buyer_snapshot_time = start_time

            logger.info(f"   🔍 Monitoring ${token_symbol} for {monitoring_duration}s "
                        f"(exit at {exit_threshold}%, buyer fade <{buyer_fade_threshold}/2min)")

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
                    elapsed = (datetime.utcnow() - start_time).total_seconds()

                    # === PRICE FADE CHECK ===
                    if current_price > 0 and not exit_alert_sent:
                        price_change_pct = ((current_price - signal_price) / signal_price) * 100

                        logger.debug(
                            f"   📊 ${token_symbol} check {checks_performed}: "
                            f"{price_change_pct:+.1f}% ({elapsed:.0f}s elapsed)"
                        )

                        if price_change_pct <= exit_threshold:
                            logger.warning("\n" + "🚨" * 30)
                            logger.warning(f"   🚨 EXIT ALERT: ${token_symbol}")
                            logger.warning(f"   📉 Price dropped {price_change_pct:.1f}% in {elapsed:.0f}s")
                            logger.warning(f"   💵 Signal price: ${signal_price:.8f}")
                            logger.warning(f"   💵 Current price: ${current_price:.8f}")
                            logger.warning(f"   🎯 Score at signal: {signal_score}/100")
                            logger.warning("🚨" * 30 + "\n")

                            if (mon_cfg['send_telegram_alert'] and
                                self.telegram_poster and config.ENABLE_TELEGRAM):
                                await self._send_alert(
                                    alert_type='exit',
                                    token_symbol=token_symbol,
                                    token_address=token_address,
                                    price_change_pct=price_change_pct,
                                    elapsed_seconds=elapsed,
                                    signal_price=signal_price,
                                    current_price=current_price
                                )

                            exit_alert_sent = True

                    # === BUYER VELOCITY FADE CHECK ===
                    if buyer_fade_enabled and self.pump_monitor and not fade_alert_sent:
                        now = datetime.utcnow()
                        time_since_snapshot = (now - last_buyer_snapshot_time).total_seconds()

                        if time_since_snapshot >= buyer_fade_window:
                            current_buyers = len(
                                self.pump_monitor.unique_buyers.get(token_address, set())
                            )
                            new_buyers = current_buyers - last_buyer_snapshot

                            logger.debug(
                                f"   👥 Buyer check: {new_buyers} new in {time_since_snapshot:.0f}s "
                                f"(need {buyer_fade_threshold}+)"
                            )

                            if new_buyers < buyer_fade_threshold and elapsed > 60:
                                # Buyer velocity has faded
                                logger.warning(f"   ⚠️  BUYER FADE: ${token_symbol} - only {new_buyers} new buyers in {time_since_snapshot:.0f}s")

                                if (mon_cfg['send_telegram_alert'] and
                                    self.telegram_poster and config.ENABLE_TELEGRAM):
                                    price_change_pct = 0
                                    if current_price > 0:
                                        price_change_pct = ((current_price - signal_price) / signal_price) * 100

                                    await self._send_alert(
                                        alert_type='fade',
                                        token_symbol=token_symbol,
                                        token_address=token_address,
                                        price_change_pct=price_change_pct,
                                        elapsed_seconds=elapsed,
                                        signal_price=signal_price,
                                        current_price=current_price,
                                        new_buyers=new_buyers,
                                        buyer_window_seconds=time_since_snapshot
                                    )

                                fade_alert_sent = True

                            # Update snapshot for next window
                            last_buyer_snapshot = current_buyers
                            last_buyer_snapshot_time = now

                except Exception as e:
                    logger.error(f"   ❌ Error checking ${token_symbol}: {e}")
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

    async def _send_alert(
        self,
        alert_type: str,
        token_symbol: str,
        token_address: str,
        price_change_pct: float,
        elapsed_seconds: float,
        signal_price: float,
        current_price: float,
        new_buyers: int = 0,
        buyer_window_seconds: float = 0
    ):
        """
        Send Telegram alert (exit or fade)
        """
        try:
            if alert_type == 'exit':
                message = (
                    f"🚨 <b>EXIT ALERT</b> 🚨\n\n"
                    f"<b>Token:</b> ${token_symbol}\n"
                    f"<b>Address:</b> <code>{token_address}</code>\n\n"
                    f"📉 <b>Price dropped {price_change_pct:.1f}% in {elapsed_seconds/60:.1f} minutes</b>\n\n"
                    f"💵 Signal price: ${signal_price:.8f}\n"
                    f"💵 Current price: ${current_price:.8f}\n\n"
                    f"⚠️ Consider taking profits or exiting position\n\n"
                    f'<a href="https://dexscreener.com/solana/{token_address}">View on DexScreener</a>'
                )
            else:  # fade
                message = (
                    f"⚠️ <b>FADE ALERT</b> ⚠️\n\n"
                    f"<b>Token:</b> ${token_symbol}\n"
                    f"<b>Address:</b> <code>{token_address}</code>\n\n"
                    f"👥 <b>Buyer velocity fading: only {new_buyers} new buyers "
                    f"in {buyer_window_seconds/60:.0f} min</b>\n"
                    f"📊 Price: {price_change_pct:+.1f}% since signal\n\n"
                    f"💵 Signal price: ${signal_price:.8f}\n"
                    f"💵 Current price: ${current_price:.8f}\n\n"
                    f"⚠️ Momentum may be dying - watch closely\n\n"
                    f'<a href="https://dexscreener.com/solana/{token_address}">View on DexScreener</a>'
                )

            await self.telegram_poster.send_message(message)
            logger.info(f"   ✅ {alert_type.upper()} alert sent to Telegram for ${token_symbol}")

        except Exception as e:
            logger.error(f"   ❌ Error sending {alert_type} alert: {e}")

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


def get_post_call_monitor(dexscreener_fetcher=None, telegram_poster=None, pump_monitor=None) -> PostCallMonitor:
    """
    Get or create singleton PostCallMonitor instance
    """
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PostCallMonitor(
            dexscreener_fetcher=dexscreener_fetcher,
            telegram_poster=telegram_poster,
            pump_monitor=pump_monitor
        )
    elif pump_monitor and not _monitor_instance.pump_monitor:
        # Update pump_monitor if provided later
        _monitor_instance.pump_monitor = pump_monitor
    return _monitor_instance
