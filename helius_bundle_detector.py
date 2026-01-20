"""
Enhanced Bundle Detector - Uses Helius transaction data for accurate detection
More reliable than PumpPortal for detecting coordinated sniper attacks
"""
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
from loguru import logger


class HeliusBundleDetector:
    """
    Detects bundled transactions using Helius enhanced transaction data
    
    More accurate than PumpPortal because:
    - Has precise slot/block numbers
    - Shows exact transaction timing
    - Can detect same-second transactions
    """
    
    def __init__(self):
        self.detected_bundles = {}  # token -> bundle data
    
    def detect_from_helius_webhook(
        self,
        token_address: str,
        webhook_transactions: List[Dict],
        unique_buyers: int = 0
    ) -> Dict:
        """
        Detect bundles from Helius webhook transaction data
        
        Args:
            token_address: Token mint address
            webhook_transactions: List of Helius enhanced transactions
            unique_buyers: Current unique buyer count
            
        Returns:
            {
                'severity': 'none'|'minor'|'medium'|'massive',
                'penalty': -5 to -40,
                'same_slot_count': int,
                'override_applied': bool,
                'reason': str
            }
        """
        if not webhook_transactions or len(webhook_transactions) < 5:
            return {
                'severity': 'none',
                'penalty': 0,
                'same_slot_count': 0,
                'override_applied': False,
                'reason': 'Not enough transactions'
            }
        
        # Group transactions by slot (Solana block)
        slots = defaultdict(list)
        
        for tx in webhook_transactions:
            slot = tx.get('slot')
            if not slot:
                continue
            
            # Only count buy transactions (receiving tokens)
            token_transfers = tx.get('tokenTransfers', [])
            fee_payer = tx.get('feePayer', '')
            
            for transfer in token_transfers:
                to_address = transfer.get('toUserAccount', '')
                token_mint = transfer.get('mint', '')
                
                # If someone received this token
                if to_address and token_mint == token_address:
                    slots[slot].append({
                        'buyer': to_address,
                        'amount': transfer.get('tokenAmount', 0),
                        'timestamp': tx.get('timestamp', 0),
                        'signature': tx.get('signature', '')
                    })
        
        if not slots:
            return {
                'severity': 'none',
                'penalty': 0,
                'same_slot_count': 0,
                'override_applied': False,
                'reason': 'No buy transactions found'
            }
        
        # Find largest bundle
        max_bundle_size = max(len(buyers) for buyers in slots.values())
        
        # Count how many slots have >3 transactions (bundled blocks)
        bundled_slots = sum(1 for buyers in slots.values() if len(buyers) > 3)
        
        # Classify severity
        if max_bundle_size <= 3:
            severity = 'none'
            base_penalty = 0
        elif max_bundle_size <= 10:
            severity = 'minor'
            base_penalty = -10
        elif max_bundle_size <= 20:
            severity = 'medium'
            base_penalty = -25
        else:
            severity = 'massive'
            base_penalty = -40
        
        # SMART OVERRIDE: High unique buyers = organic
        override_applied = False
        final_penalty = base_penalty
        
        if unique_buyers > 100 and base_penalty < 0:
            final_penalty = base_penalty // 2
            override_applied = True
            logger.info(f"   🔓 Bundle override: {unique_buyers} buyers (reduced {base_penalty} → {final_penalty})")
        elif unique_buyers > 50 and base_penalty <= -25:
            final_penalty = base_penalty + 10
            override_applied = True
        
        result = {
            'severity': severity,
            'penalty': final_penalty,
            'same_slot_count': max_bundle_size,
            'bundled_slots': bundled_slots,
            'total_slots': len(slots),
            'override_applied': override_applied,
            'reason': f'{severity.upper()}: {max_bundle_size} txs in same slot'
        }
        
        # Cache result
        self.detected_bundles[token_address] = {
            **result,
            'detected_at': datetime.utcnow()
        }
        
        return result
    
    def detect_from_transaction_list(
        self,
        token_address: str,
        transactions: List[Dict],
        unique_buyers: int = 0
    ) -> Dict:
        """
        Alternative: Detect bundles from any list of transaction data
        
        Expects transactions with: slot, timestamp, buyer, amount
        """
        if not transactions or len(transactions) < 5:
            return {
                'severity': 'none',
                'penalty': 0,
                'same_slot_count': 0,
                'override_applied': False,
                'reason': 'Not enough transactions'
            }
        
        # Group by slot/block
        slots = defaultdict(list)
        
        for tx in transactions:
            slot = tx.get('slot') or tx.get('block')
            if slot:
                slots[slot].append(tx)
        
        # Find max bundle
        max_bundle_size = max(len(txs) for txs in slots.values()) if slots else 0
        
        # Classify
        if max_bundle_size <= 3:
            severity = 'none'
            penalty = 0
        elif max_bundle_size <= 10:
            severity = 'minor'
            penalty = -10
        elif max_bundle_size <= 20:
            severity = 'medium'
            penalty = -25
        else:
            severity = 'massive'
            penalty = -40
        
        # Override logic
        override_applied = False
        if unique_buyers > 100 and penalty < 0:
            penalty = penalty // 2
            override_applied = True
        elif unique_buyers > 50 and penalty <= -25:
            penalty = penalty + 10
            override_applied = True
        
        return {
            'severity': severity,
            'penalty': penalty,
            'same_slot_count': max_bundle_size,
            'override_applied': override_applied,
            'reason': f'{severity.upper()}: {max_bundle_size} txs in same slot'
        }
    
    def get_bundle_data(self, token_address: str) -> Optional[Dict]:
        """Get cached bundle detection data for a token"""
        return self.detected_bundles.get(token_address)
