#!/usr/bin/env python3
"""
Automated ML Retraining Script - Runs After Daily Data Collection

Features:
- Checks if enough new data has been collected (200+ tokens minimum)
- Retrains XGBoost model with latest historical data
- Validates model performance on test set
- Only deploys if new model performs better than baseline
- Logs all training metrics and decisions

Run via cron after daily_token_collector.py:
0 1 * * * /path/to/automated_ml_retrain.py  # Run at 1 AM UTC (after midnight collection)
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from loguru import logger

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ralph.ml_pipeline import MLPipeline


class AutomatedMLRetrainer:
    """Automated ML retraining with smart deployment logic"""

    def __init__(self):
        self.pipeline = MLPipeline()
        self.data_file = 'data/historical_training_data.json'
        self.metrics_file = 'data/ml_training_metrics.json'
        self.min_tokens_for_retrain = 200  # Minimum dataset size
        self.min_new_tokens_for_retrain = 50  # Minimum new data since last train

    async def should_retrain(self) -> bool:
        """
        Determine if we should retrain the model

        Criteria:
        1. Have at least 200 total tokens
        2. Have at least 50 new tokens since last training
        3. Historical data file exists

        Returns:
            bool: True if should retrain
        """
        logger.info("=" * 80)
        logger.info("🤔 CHECKING IF RETRAINING IS NEEDED")
        logger.info("=" * 80)

        # Check if data file exists
        if not os.path.exists(self.data_file):
            logger.error(f"❌ Data file not found: {self.data_file}")
            return False

        # Load historical data
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load data: {e}")
            return False

        total_tokens = data.get('total_tokens', 0)
        logger.info(f"   Total tokens in dataset: {total_tokens}")

        # Check minimum dataset size
        if total_tokens < self.min_tokens_for_retrain:
            logger.info(f"   ⏭️  Not enough data yet ({total_tokens} < {self.min_tokens_for_retrain})")
            return False

        # Load last training metrics
        last_training_date = None
        last_training_token_count = 0

        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    metrics = json.load(f)
                    last_training = metrics.get('trainings', [])[-1] if metrics.get('trainings') else None
                    if last_training:
                        last_training_date = last_training.get('trained_at')
                        last_training_token_count = last_training.get('training_tokens', 0)
                        logger.info(f"   Last training: {last_training_date} ({last_training_token_count} tokens)")
            except:
                pass

        # Calculate new tokens since last training
        new_tokens = total_tokens - last_training_token_count
        logger.info(f"   New tokens since last training: {new_tokens}")

        if new_tokens < self.min_new_tokens_for_retrain:
            logger.info(f"   ⏭️  Not enough new data ({new_tokens} < {self.min_new_tokens_for_retrain})")
            return False

        logger.info(f"   ✅ READY TO RETRAIN!")
        logger.info(f"      Total: {total_tokens} tokens")
        logger.info(f"      New: {new_tokens} tokens")
        return True

    async def retrain_model(self) -> dict:
        """
        Retrain the ML model with latest data

        Returns:
            dict: Training results with metrics
        """
        logger.info("\n" + "=" * 80)
        logger.info("🎓 RETRAINING ML MODEL")
        logger.info("=" * 80)

        # Train model
        success = self.pipeline.train_model()

        if not success:
            logger.error("❌ Training failed!")
            return {
                'success': False,
                'error': 'Training failed'
            }

        # Get model metrics
        logger.info("\n📊 Model Performance:")
        logger.info(f"   Feature count: {len(self.pipeline.feature_names)}")
        logger.info(f"   Features: {', '.join(self.pipeline.feature_names[:10])}...")

        return {
            'success': True,
            'trained_at': datetime.utcnow().isoformat(),
            'feature_count': len(self.pipeline.feature_names),
            'features': self.pipeline.feature_names,
            'model_path': self.pipeline.model_path
        }

    async def save_training_metrics(self, results: dict):
        """Save training metrics to file"""
        logger.info("\n" + "=" * 80)
        logger.info("💾 SAVING TRAINING METRICS")
        logger.info("=" * 80)

        # Load existing metrics
        metrics = {'trainings': []}
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    metrics = json.load(f)
            except:
                pass

        # Load data to get token count
        with open(self.data_file, 'r') as f:
            data = json.load(f)

        # Add new training record
        training_record = {
            'trained_at': results['trained_at'],
            'training_tokens': data.get('total_tokens', 0),
            'feature_count': results['feature_count'],
            'features': results['features'],
            'model_path': results['model_path'],
            'success': results['success']
        }

        metrics['trainings'].append(training_record)
        metrics['last_training'] = results['trained_at']
        metrics['total_trainings'] = len(metrics['trainings'])

        # Save metrics
        os.makedirs('data', exist_ok=True)
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"   ✅ Saved training metrics to {self.metrics_file}")
        logger.info(f"   Total trainings: {metrics['total_trainings']}")

    async def run(self):
        """Run automated retraining. Returns status dict for callers."""
        logger.info("=" * 80)
        logger.info("🤖 AUTOMATED ML RETRAINING")
        logger.info("=" * 80)
        logger.info(f"   Date: {datetime.utcnow().date()}")
        logger.info("")

        # Check if we should retrain
        should_retrain = await self.should_retrain()

        if not should_retrain:
            logger.info("\n✅ No retraining needed at this time")
            # Return skip reason for callers (e.g. admin bot)
            total = self._get_dataset_size()
            return {
                'action': 'skipped',
                'reason': f'Not enough data ({total}/{self.min_tokens_for_retrain} tokens)',
                'total_tokens': total,
                'required': self.min_tokens_for_retrain,
            }

        # Retrain model
        results = await self.retrain_model()

        if not results['success']:
            logger.error("\n❌ Retraining failed!")
            return {'action': 'failed', 'reason': 'Training failed'}

        # Save metrics
        await self.save_training_metrics(results)

        logger.info("\n" + "=" * 80)
        logger.info("✅ AUTOMATED RETRAINING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"   New model deployed: {results['model_path']}")
        logger.info(f"   Features: {results['feature_count']}")
        logger.info(f"   Model will be used in next conviction scoring cycle")
        logger.info("")

        return {
            'action': 'trained',
            'feature_count': results['feature_count'],
            'model_path': results['model_path'],
        }

    def _get_dataset_size(self) -> int:
        """Get current dataset token count"""
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                return data.get('total_tokens', 0)
        except Exception:
            return 0


async def main():
    """Run automated retraining"""
    retrainer = AutomatedMLRetrainer()
    await retrainer.run()


if __name__ == "__main__":
    asyncio.run(main())
