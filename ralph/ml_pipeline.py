#!/usr/bin/env python3
"""
ML Pipeline for Ralph
Trains XGBoost models on collected token data and makes predictions

Features extracted:
- KOL count and tier distribution
- Holder concentration metrics
- Volume/liquidity ratios
- Security scores
- Timing/momentum features
- Narrative matches

Predicts:
- Outcome class: 0=rug, 1=2x, 2=10x, 3=50x, 4=100x+
- Win probability (0-1)
"""
import json
import os
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from loguru import logger
import numpy as np

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    HAS_ML = True
except ImportError:
    logger.warning("⚠️  XGBoost not installed. Run: pip install xgboost scikit-learn")
    HAS_ML = False


class MLPipeline:
    """ML training and prediction pipeline"""

    def __init__(self, data_file: str = 'external_data.json', model_dir: str = 'models'):
        self.data_file = data_file
        self.model_dir = model_dir
        self.model = None
        self.feature_names = []

        # Create models directory
        os.makedirs(self.model_dir, exist_ok=True)

    def load_data(self) -> List[Dict]:
        """Load scraped token data"""
        if not os.path.exists(self.data_file):
            logger.error(f"❌ Data file not found: {self.data_file}")
            logger.error("   Run ralph/scrape_external_data.py first")
            return []

        with open(self.data_file, 'r') as f:
            data = json.load(f)

        tokens = data.get('tokens', [])
        logger.info(f"✅ Loaded {len(tokens)} tokens from {self.data_file}")
        return tokens

    def extract_features(self, token: Dict) -> Dict:
        """
        Extract ML features from a token

        Returns:
            Dict of feature_name: value
        """
        features = {}

        # KOL features
        features['kol_count'] = token.get('our_kol_count', 0)
        features['new_wallet_count'] = token.get('new_wallet_count', 0)

        # Holder metrics
        onchain = token.get('onchain_metrics', {})
        features['holder_count'] = onchain.get('holder_count', 0)
        features['top_10_concentration'] = onchain.get('top_10_concentration_pct', 0)
        features['top_3_concentration'] = onchain.get('top_3_concentration_pct', 0)
        features['decentralization_score'] = onchain.get('decentralization_score', 0)

        # Volume/Liquidity
        features['volume_24h'] = token.get('volume_24h', 0)
        features['liquidity_usd'] = token.get('liquidity_usd', 0)
        features['volume_to_liquidity'] = (
            features['volume_24h'] / features['liquidity_usd']
            if features['liquidity_usd'] > 0 else 0
        )

        # Price momentum
        features['price_change_24h'] = token.get('price_change_24h', 0)
        features['price_change_6h'] = token.get('price_change_6h', 0)
        features['price_change_1h'] = token.get('price_change_1h', 0)

        # Security
        security = token.get('security', {})
        features['rugcheck_score'] = security.get('rugcheck_score', 0)
        features['is_rugged'] = 1 if security.get('rugged', False) else 0
        features['is_honeypot'] = 1 if security.get('is_honeypot', False) else 0

        # Risk level encoding (0=good, 1=low, 2=medium, 3=high, 4=critical)
        risk_map = {'good': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        features['risk_level'] = risk_map.get(security.get('risk_level', 'medium'), 2)

        # Token age (if available)
        if token.get('created_at'):
            try:
                created = datetime.fromtimestamp(token['created_at'] / 1000)
                age_hours = (datetime.utcnow() - created).total_seconds() / 3600
                features['token_age_hours'] = age_hours
            except:
                features['token_age_hours'] = 0
        else:
            features['token_age_hours'] = 0

        return features

    def classify_outcome(self, token: Dict) -> int:
        """
        Classify token outcome for training

        Returns:
            0 = rug/failed
            1 = 2x (100-300%)
            2 = 10x (300-900%)
            3 = 50x (900-4900%)
            4 = 100x+ (5000%+)
        """
        # Check if rugged
        security = token.get('security', {})
        if security.get('rugged') or security.get('is_honeypot'):
            return 0

        # Classify by price change
        gain = token.get('price_change_24h', 0)

        if gain < 100:  # Less than 2x
            return 0  # Failed/rug
        elif gain < 300:
            return 1  # 2x
        elif gain < 900:
            return 2  # 10x
        elif gain < 4900:
            return 3  # 50x
        else:
            return 4  # 100x+

    def prepare_training_data(self, tokens: List[Dict]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare features and labels for training

        Returns:
            (X, y, feature_names)
        """
        logger.info("🔧 Extracting features and labels...")

        features_list = []
        labels = []

        for token in tokens:
            try:
                features = self.extract_features(token)
                label = self.classify_outcome(token)

                features_list.append(features)
                labels.append(label)
            except Exception as e:
                logger.warning(f"⚠️  Failed to process token {token.get('symbol', 'UNKNOWN')}: {e}")
                continue

        # Convert to arrays
        if not features_list:
            raise ValueError("No valid tokens to train on!")

        feature_names = list(features_list[0].keys())
        X = np.array([[f[name] for name in feature_names] for f in features_list])
        y = np.array(labels)

        logger.info(f"✅ Prepared {len(X)} samples with {len(feature_names)} features")
        logger.info(f"   Features: {', '.join(feature_names)}")

        # Show class distribution
        unique, counts = np.unique(y, return_counts=True)
        class_names = ['Rug/Fail', '2x', '10x', '50x', '100x+']
        logger.info("   Class distribution:")
        for cls, count in zip(unique, counts):
            logger.info(f"      {class_names[cls]}: {count} ({count/len(y)*100:.1f}%)")

        return X, y, feature_names

    def train(self, tokens: Optional[List[Dict]] = None):
        """Train XGBoost model on token data"""
        if not HAS_ML:
            logger.error("❌ XGBoost not available. Install with: pip install xgboost scikit-learn")
            return False

        # Load data if not provided
        if tokens is None:
            tokens = self.load_data()

        if len(tokens) < 50:
            logger.error(f"❌ Need at least 50 tokens to train. Only have {len(tokens)}")
            return False

        # Prepare data
        X, y, feature_names = self.prepare_training_data(tokens)
        self.feature_names = feature_names

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"\n🎓 Training XGBoost model...")
        logger.info(f"   Training samples: {len(X_train)}")
        logger.info(f"   Test samples: {len(X_test)}")

        # Train model
        self.model = xgb.XGBClassifier(
            objective='multi:softmax',
            num_class=5,  # 0-4
            max_depth=6,
            learning_rate=0.1,
            n_estimators=100,
            random_state=42
        )

        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        logger.info(f"\n✅ Model trained!")
        logger.info(f"   Accuracy: {accuracy*100:.1f}%")

        # Detailed report
        class_names = ['Rug/Fail', '2x', '10x', '50x', '100x+']
        report = classification_report(y_test, y_pred, target_names=class_names, zero_division=0)
        logger.info(f"\n{report}")

        # Feature importance
        importances = self.model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]

        logger.info("\n📊 Top 10 Most Important Features:")
        for i in sorted_idx[:10]:
            logger.info(f"   {feature_names[i]}: {importances[i]:.4f}")

        # Save model
        self.save_model()

        return True

    def predict(self, token_features: Dict) -> Tuple[int, float]:
        """
        Predict outcome for a token

        Args:
            token_features: Dict of features (from extract_features)

        Returns:
            (predicted_class, confidence)
        """
        if self.model is None:
            self.load_model()

        if self.model is None:
            logger.warning("⚠️  No model available for prediction")
            return (0, 0.0)

        # Convert features to array
        X = np.array([[token_features.get(name, 0) for name in self.feature_names]])

        # Predict
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        confidence = probabilities[prediction]

        return (int(prediction), float(confidence))

    def save_model(self):
        """Save model and metadata"""
        if self.model is None:
            logger.warning("⚠️  No model to save")
            return

        model_path = os.path.join(self.model_dir, 'xgboost_model.pkl')
        metadata_path = os.path.join(self.model_dir, 'model_metadata.json')

        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)

        # Save metadata
        metadata = {
            'feature_names': self.feature_names,
            'trained_at': datetime.utcnow().isoformat(),
            'model_type': 'XGBoost',
            'num_classes': 5,
            'class_names': ['Rug/Fail', '2x', '10x', '50x', '100x+']
        }

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"💾 Model saved to {model_path}")

    def load_model(self):
        """Load trained model"""
        model_path = os.path.join(self.model_dir, 'xgboost_model.pkl')
        metadata_path = os.path.join(self.model_dir, 'model_metadata.json')

        if not os.path.exists(model_path):
            logger.warning("⚠️  No trained model found. Run train() first.")
            return False

        # Load model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        self.feature_names = metadata['feature_names']

        logger.info(f"✅ Model loaded from {model_path}")
        logger.info(f"   Trained: {metadata['trained_at']}")

        return True


def main():
    """Main entry point for ML pipeline"""
    import argparse

    parser = argparse.ArgumentParser(description='ML Pipeline for Ralph')
    parser.add_argument('--train', action='store_true', help='Train new model')
    parser.add_argument('--retrain', action='store_true', help='Retrain on latest data')
    parser.add_argument('--test', action='store_true', help='Test predictions')

    args = parser.parse_args()

    pipeline = MLPipeline()

    if args.train or args.retrain:
        logger.info("🚀 Starting ML training pipeline...")
        success = pipeline.train()

        if success:
            logger.info("\n✅ Training complete! Model ready for predictions.")
        else:
            logger.error("\n❌ Training failed")
            return 1

    elif args.test:
        # Test prediction
        pipeline.load_model()

        # Example features
        test_features = {
            'kol_count': 3,
            'holder_count': 500,
            'top_10_concentration': 25,
            'liquidity_usd': 100000,
            'volume_24h': 500000,
            'rugcheck_score': 3,
            'risk_level': 1
        }

        prediction, confidence = pipeline.predict(test_features)
        class_names = ['Rug/Fail', '2x', '10x', '50x', '100x+']

        logger.info(f"\n🎯 Prediction: {class_names[prediction]}")
        logger.info(f"   Confidence: {confidence*100:.1f}%")

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    exit(main())
