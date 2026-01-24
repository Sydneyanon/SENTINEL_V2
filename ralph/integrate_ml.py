#!/usr/bin/env python3
"""
Integrate ML Predictions into Conviction Engine
Adds ML win probability predictions to token scoring
"""
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ralph.ml_pipeline import MLPipeline
from typing import Dict
from loguru import logger


class MLPredictor:
    """Singleton ML predictor for conviction engine"""

    _instance = None
    _model_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.pipeline = MLPipeline()
        return cls._instance

    def load_model(self):
        """Load ML model (called once at startup)"""
        if not self._model_loaded:
            success = self.pipeline.load_model()
            self._model_loaded = success
            if success:
                logger.info("✅ ML model loaded for predictions")
            else:
                logger.warning("⚠️  ML model not available - predictions disabled")
        return self._model_loaded

    def predict_for_signal(self, token_data: Dict, kol_count: int) -> Dict:
        """
        Make ML prediction for a signal

        Args:
            token_data: Token data from signal
            kol_count: Number of KOLs who bought

        Returns:
            {
                'prediction_class': int (0-4),
                'class_name': str ('2x', '10x', etc),
                'confidence': float (0-1),
                'ml_bonus': int (conviction points to add),
                'ml_enabled': bool
            }
        """
        if not self._model_loaded:
            return {
                'prediction_class': 0,
                'class_name': 'unknown',
                'confidence': 0.0,
                'ml_bonus': 0,
                'ml_enabled': False
            }

        try:
            # Build feature dict from token data
            features = {
                'kol_count': kol_count,
                'new_wallet_count': 0,  # Not tracked yet
                'holder_count': token_data.get('holder_count', 0),
                'top_10_concentration': token_data.get('top_10_concentration_pct', 0),
                'top_3_concentration': token_data.get('top_3_concentration_pct', 0),
                'decentralization_score': token_data.get('decentralization_score', 0),
                'volume_24h': token_data.get('volume', 0),
                'liquidity_usd': token_data.get('liquidity', 0),
                'volume_to_liquidity': (
                    token_data.get('volume', 0) / token_data.get('liquidity', 1)
                    if token_data.get('liquidity', 0) > 0 else 0
                ),
                'price_change_24h': 0,  # Not available for new tokens
                'price_change_6h': 0,
                'price_change_1h': 0,
                'rugcheck_score': 0,  # Would come from RugCheck if available
                'is_rugged': 0,
                'is_honeypot': 0,
                'risk_level': 2,  # Default medium
                'token_age_hours': 0  # New token
            }

            # Get prediction
            prediction, confidence = self.pipeline.predict(features)

            class_names = ['Rug/Fail', '2x', '10x', '50x', '100x+']

            # Calculate conviction bonus based on prediction
            # Higher prediction = more bonus points
            # High confidence = more bonus
            if prediction >= 4:  # 100x+
                base_bonus = 20
            elif prediction >= 3:  # 50x
                base_bonus = 15
            elif prediction >= 2:  # 10x
                base_bonus = 10
            elif prediction >= 1:  # 2x
                base_bonus = 5
            else:  # Rug/fail
                base_bonus = -30  # PENALTY for predicted rugs

            # Adjust by confidence
            ml_bonus = int(base_bonus * confidence)

            return {
                'prediction_class': prediction,
                'class_name': class_names[prediction],
                'confidence': confidence,
                'ml_bonus': ml_bonus,
                'ml_enabled': True
            }

        except Exception as e:
            logger.error(f"❌ ML prediction failed: {e}")
            return {
                'prediction_class': 0,
                'class_name': 'error',
                'confidence': 0.0,
                'ml_bonus': 0,
                'ml_enabled': False
            }


# Singleton instance
_predictor = None


def get_ml_predictor() -> MLPredictor:
    """Get singleton ML predictor"""
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor()
        _predictor.load_model()
    return _predictor


if __name__ == "__main__":
    # Test the predictor
    predictor = get_ml_predictor()

    test_token = {
        'holder_count': 500,
        'liquidity': 100000,
        'volume': 500000
    }

    result = predictor.predict_for_signal(test_token, kol_count=3)

    print(f"\n🎯 ML Prediction Test:")
    print(f"   Class: {result['class_name']}")
    print(f"   Confidence: {result['confidence']*100:.1f}%")
    print(f"   Conviction Bonus: {result['ml_bonus']:+d} points")
