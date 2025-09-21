"""
Virality scoring model for predicting meme popularity.
Uses XGBoost/Logistic Regression with features extracted from memes.
"""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
from app.config import config

# Try to import ML libraries, use simple fallback if not available
try:
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    np = None
    RandomForestRegressor = None
    StandardScaler = None
    train_test_split = None
    mean_squared_error = None
    r2_score = None
    joblib = None
    SKLEARN_AVAILABLE = False

class ViralityPredictor:
    """ML-based virality prediction system for memes."""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.model_path = "data/virality_model.pkl"
        self.scaler_path = "data/virality_scaler.pkl"
        
        # Try to load existing model, or train a new one
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize or load the virality prediction model."""
        try:
            if SKLEARN_AVAILABLE and self._load_existing_model():
                logger.info("Loaded existing virality model")
            elif SKLEARN_AVAILABLE:
                logger.info("Training new virality model with sample data")
                self._train_model_with_sample_data()
            else:
                logger.info("Scikit-learn not available, using simple fallback model")
                self._create_fallback_model()
        except Exception as e:
            logger.error(f"Error initializing virality model: {e}")
            # Create a simple fallback model
            self._create_fallback_model()
    
    def _load_existing_model(self) -> bool:
        """Load existing trained model if available."""
        try:
            if not SKLEARN_AVAILABLE or not joblib:
                return False
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to load existing model: {e}")
            return False
    
    def _save_model(self):
        """Save trained model and scaler."""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info("Model and scaler saved successfully")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def _create_sample_dataset(self) -> Dict[str, List]:
        """Create sample dataset for training the virality model."""
        # Sample meme data with various features that might predict virality
        sample_data = [
            # Template popularity, caption length, humor style, keyword match score, upvotes, virality_score
            {"template_popularity": 95, "caption_length": 25, "humor_style_encoded": 1, "keyword_match_score": 0.8, "template_familiarity": 90, "time_of_day": 14, "weekday": 2, "upvotes": 1250, "virality_score": 88},
            {"template_popularity": 87, "caption_length": 18, "humor_style_encoded": 2, "keyword_match_score": 0.7, "template_familiarity": 85, "time_of_day": 19, "weekday": 5, "upvotes": 890, "virality_score": 76},
            {"template_popularity": 92, "caption_length": 31, "humor_style_encoded": 0, "keyword_match_score": 0.9, "template_familiarity": 88, "time_of_day": 12, "weekday": 1, "upvotes": 2100, "virality_score": 95},
            {"template_popularity": 78, "caption_length": 45, "humor_style_encoded": 3, "keyword_match_score": 0.6, "template_familiarity": 70, "time_of_day": 8, "weekday": 0, "upvotes": 420, "virality_score": 52},
            {"template_popularity": 83, "caption_length": 22, "humor_style_encoded": 1, "keyword_match_score": 0.75, "template_familiarity": 80, "time_of_day": 16, "weekday": 4, "upvotes": 650, "virality_score": 68},
            {"template_popularity": 96, "caption_length": 15, "humor_style_encoded": 2, "keyword_match_score": 0.85, "template_familiarity": 92, "time_of_day": 20, "weekday": 6, "upvotes": 1850, "virality_score": 91},
            {"template_popularity": 71, "caption_length": 38, "humor_style_encoded": 4, "keyword_match_score": 0.5, "template_familiarity": 65, "time_of_day": 6, "weekday": 3, "upvotes": 280, "virality_score": 41},
            {"template_popularity": 89, "caption_length": 27, "humor_style_encoded": 0, "keyword_match_score": 0.8, "template_familiarity": 86, "time_of_day": 15, "weekday": 2, "upvotes": 1120, "virality_score": 82},
            {"template_popularity": 94, "caption_length": 20, "humor_style_encoded": 1, "keyword_match_score": 0.9, "template_familiarity": 91, "time_of_day": 18, "weekday": 5, "upvotes": 1670, "virality_score": 89},
            {"template_popularity": 76, "caption_length": 42, "humor_style_encoded": 3, "keyword_match_score": 0.4, "template_familiarity": 72, "time_of_day": 10, "weekday": 1, "upvotes": 310, "virality_score": 38},
            {"template_popularity": 88, "caption_length": 24, "humor_style_encoded": 2, "keyword_match_score": 0.7, "template_familiarity": 84, "time_of_day": 21, "weekday": 0, "upvotes": 780, "virality_score": 71},
            {"template_popularity": 81, "caption_length": 35, "humor_style_encoded": 4, "keyword_match_score": 0.6, "template_familiarity": 78, "time_of_day": 9, "weekday": 6, "upvotes": 490, "virality_score": 59},
            {"template_popularity": 93, "caption_length": 19, "humor_style_encoded": 0, "keyword_match_score": 0.85, "template_familiarity": 89, "time_of_day": 13, "weekday": 4, "upvotes": 1450, "virality_score": 86},
            {"template_popularity": 74, "caption_length": 48, "humor_style_encoded": 3, "keyword_match_score": 0.45, "template_familiarity": 68, "time_of_day": 7, "weekday": 3, "upvotes": 230, "virality_score": 33},
            {"template_popularity": 91, "caption_length": 16, "humor_style_encoded": 1, "keyword_match_score": 0.8, "template_familiarity": 87, "time_of_day": 17, "weekday": 2, "upvotes": 1340, "virality_score": 84},
            {"template_popularity": 86, "caption_length": 29, "humor_style_encoded": 2, "keyword_match_score": 0.65, "template_familiarity": 82, "time_of_day": 22, "weekday": 1, "upvotes": 620, "virality_score": 64},
            {"template_popularity": 79, "caption_length": 40, "humor_style_encoded": 4, "keyword_match_score": 0.55, "template_familiarity": 75, "time_of_day": 11, "weekday": 5, "upvotes": 380, "virality_score": 47},
            {"template_popularity": 97, "caption_length": 21, "humor_style_encoded": 0, "keyword_match_score": 0.95, "template_familiarity": 94, "time_of_day": 19, "weekday": 6, "upvotes": 2300, "virality_score": 97},
            {"template_popularity": 73, "caption_length": 44, "humor_style_encoded": 3, "keyword_match_score": 0.4, "template_familiarity": 69, "time_of_day": 5, "weekday": 0, "upvotes": 190, "virality_score": 29},
            {"template_popularity": 90, "caption_length": 26, "humor_style_encoded": 1, "keyword_match_score": 0.75, "template_familiarity": 88, "time_of_day": 14, "weekday": 4, "upvotes": 950, "virality_score": 78}
        ]
        
        # Convert to format suitable for simple processing
        dataset = {
            "template_popularity": [d["template_popularity"] for d in sample_data],
            "caption_length": [d["caption_length"] for d in sample_data],
            "humor_style_encoded": [d["humor_style_encoded"] for d in sample_data],
            "keyword_match_score": [d["keyword_match_score"] for d in sample_data],
            "template_familiarity": [d["template_familiarity"] for d in sample_data],
            "time_of_day": [d["time_of_day"] for d in sample_data],
            "weekday": [d["weekday"] for d in sample_data],
            "virality_score": [d["virality_score"] for d in sample_data]
        }
        return dataset
    
    def _train_model_with_sample_data(self):
        """Train the virality prediction model using sample data."""
        try:
            # Create sample dataset
            data = self._create_sample_dataset()
            
            # Define features and target
            feature_columns = [
                'template_popularity', 'caption_length', 'humor_style_encoded',
                'keyword_match_score', 'template_familiarity', 'time_of_day', 'weekday'
            ]
            
            X = [[data[col][i] for col in feature_columns] for i in range(len(data['virality_score']))]
            y = data['virality_score']
            
            self.feature_names = feature_columns
            
            # Split data for validation
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train RandomForest model
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.model.fit(X_train_scaled, y_train)
            model_name = "RandomForest"
            
            # Evaluate model
            y_pred = self.model.predict(X_test_scaled)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            logger.info(f"Virality model trained ({model_name}): MSE={mse:.2f}, R²={r2:.3f}")
            
            # Save the trained model
            self._save_model()
            
        except Exception as e:
            logger.error(f"Error training virality model: {e}")
            self._create_fallback_model()
    
    def _create_fallback_model(self):
        """Create a simple fallback model for virality prediction."""
        logger.info("Creating fallback virality model")
        
        # Simple rule-based model
        class FallbackModel:
            def predict(self, X):
                # Simple heuristic based on available features
                scores = []
                for row in X:
                    # Basic scoring based on template popularity and other factors
                    score = (
                        row[0] * 0.4 +  # template_popularity
                        (50 - abs(row[1] - 25)) * 0.8 +  # caption_length (optimal around 25)
                        row[3] * 30 +  # keyword_match_score
                        row[4] * 0.3   # template_familiarity
                    )
                    scores.append(min(100, max(0, score)))
                return np.array(scores)
        
        self.model = FallbackModel()
        self.scaler = StandardScaler()
        # Fit scaler with dummy data
        dummy_data = np.random.randn(10, 7)
        self.scaler.fit(dummy_data)
        
        self.feature_names = [
            'template_popularity', 'caption_length', 'humor_style_encoded',
            'keyword_match_score', 'template_familiarity', 'time_of_day', 'weekday'
        ]
    
    def predict_virality(self, meme_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict virality score for a meme.
        
        Args:
            meme_features: Dictionary with meme features
            
        Returns:
            Dictionary with prediction results and explanations
        """
        try:
            # Extract and prepare features
            features = self._prepare_features(meme_features)
            
            if features is None:
                return {
                    "success": False,
                    "error": "Failed to prepare features",
                    "virality_score": 50.0
                }
            
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Make prediction
            virality_score = float(self.model.predict(features_scaled)[0])
            
            # Ensure score is within bounds
            virality_score = max(0.0, min(100.0, virality_score))
            
            # Generate explanation factors
            factors = self._explain_prediction(meme_features, virality_score)
            
            result = {
                "success": True,
                "virality_score": round(virality_score, 1),
                "factors": factors,
                "prediction_confidence": self._calculate_confidence(features, virality_score)
            }
            
            logger.debug(f"Predicted virality score: {virality_score:.1f}")
            return result
            
        except Exception as e:
            logger.error(f"Error predicting virality: {e}")
            return {
                "success": False,
                "error": str(e),
                "virality_score": 50.0,
                "factors": {"error": "Prediction failed"}
            }
    
    def _prepare_features(self, meme_features: Dict[str, Any]) -> Optional[List[float]]:
        """
        Prepare feature vector from meme data.
        
        Args:
            meme_features: Raw meme features
            
        Returns:
            Feature vector for prediction
        """
        try:
            # Extract features with defaults
            template_popularity = float(meme_features.get("template_popularity", 75.0))
            caption = meme_features.get("caption", "")
            caption_length = len(caption)
            
            # Encode humor style
            style = meme_features.get("style", "sarcastic")
            style_mapping = {
                "sarcastic": 0,
                "gen_z_slang": 1,
                "wholesome": 2,
                "dark_humor": 3,
                "corporate_irony": 4
            }
            humor_style_encoded = float(style_mapping.get(style, 0))
            
            # Calculate keyword match score
            keyword_match_score = self._calculate_keyword_match_score(meme_features)
            
            # Template familiarity (similar to popularity but different metric)
            template_familiarity = float(meme_features.get("template_familiarity", template_popularity * 0.9))
            
            # Time-based features
            now = datetime.now()
            time_of_day = float(now.hour)
            weekday = float(now.weekday())
            
            features = [
                template_popularity,
                caption_length,
                humor_style_encoded,
                keyword_match_score,
                template_familiarity,
                time_of_day,
                weekday
            ]
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None
    
    def _calculate_keyword_match_score(self, meme_features: Dict[str, Any]) -> float:
        """Calculate how well the meme matches trending keywords/topics."""
        try:
            # Simple keyword matching based on available data
            caption = meme_features.get("caption", "").lower()
            topic = meme_features.get("topic", "").lower()
            template_tags = meme_features.get("template_tags", [])
            
            # Count matches between topic/caption and template tags
            matches = 0
            total_tags = max(len(template_tags), 1)
            
            for tag in template_tags:
                if tag.lower() in caption or tag.lower() in topic:
                    matches += 1
            
            # Base score from matches
            match_score = matches / total_tags
            
            # Bonus for trending keywords/phrases
            trending_keywords = [
                "monday", "weekend", "work", "coffee", "meeting", "zoom", "remote",
                "tiktok", "instagram", "twitter", "meme", "viral", "trending",
                "mood", "vibe", "energy", "aesthetic", "literally", "period"
            ]
            
            trending_matches = sum(1 for keyword in trending_keywords 
                                 if keyword in caption or keyword in topic)
            trending_bonus = min(0.3, trending_matches * 0.1)
            
            final_score = min(1.0, match_score + trending_bonus)
            return final_score
            
        except Exception:
            return 0.6  # Default moderate score
    
    def _explain_prediction(self, meme_features: Dict[str, Any], virality_score: float) -> Dict[str, Any]:
        """
        Generate explanation for the virality prediction.
        
        Args:
            meme_features: Original meme features
            virality_score: Predicted score
            
        Returns:
            Dictionary with explanation factors
        """
        factors = {}
        
        # Template popularity impact
        template_pop = meme_features.get("template_popularity", 75)
        if template_pop > 85:
            factors["template"] = "High-popularity template boosts virality"
        elif template_pop < 70:
            factors["template"] = "Low-popularity template may limit reach"
        else:
            factors["template"] = "Template popularity is moderate"
        
        # Caption length impact
        caption_length = len(meme_features.get("caption", ""))
        if 15 <= caption_length <= 35:
            factors["caption_length"] = "Optimal caption length for engagement"
        elif caption_length > 50:
            factors["caption_length"] = "Caption might be too long for quick consumption"
        else:
            factors["caption_length"] = "Caption length is acceptable"
        
        # Style impact
        style = meme_features.get("style", "sarcastic")
        style_popularity = {
            "sarcastic": "High engagement style",
            "gen_z_slang": "Appeals to younger demographics", 
            "wholesome": "Broad appeal across age groups",
            "dark_humor": "Niche but loyal audience",
            "corporate_irony": "Popular among working professionals"
        }
        factors["humor_style"] = style_popularity.get(style, "Unknown style impact")
        
        # Overall prediction
        if virality_score > 80:
            factors["overall"] = "High viral potential - likely to get significant engagement"
        elif virality_score > 60:
            factors["overall"] = "Good viral potential - should perform well"
        elif virality_score > 40:
            factors["overall"] = "Moderate viral potential - decent engagement expected"
        else:
            factors["overall"] = "Low viral potential - may need optimization"
        
        return factors
    
    def _calculate_confidence(self, features: List[float], prediction: float) -> float:
        """Calculate confidence score for the prediction."""
        try:
            # Simple confidence based on feature values and prediction
            # Features closer to training data means higher confidence
            
            # Check if features are within reasonable ranges
            confidence = 0.8  # Base confidence
            
            # Adjust based on extreme values
            if features[0] < 50 or features[0] > 100:  # template_popularity out of range
                confidence -= 0.1
            if features[1] > 100:  # very long caption
                confidence -= 0.1
            if prediction < 10 or prediction > 95:  # extreme predictions
                confidence -= 0.15
                
            return max(0.5, min(0.95, confidence))
            
        except Exception:
            return 0.7  # Default moderate confidence
    
    def retrain_with_data(self, new_meme_data: List[Dict[str, Any]]):
        """
        Retrain model with new meme performance data.
        
        Args:
            new_meme_data: List of meme data with actual performance metrics
        """
        try:
            if len(new_meme_data) < 5:
                logger.warning("Not enough data for retraining")
                return
            
            # Convert new data to DataFrame
            df_new = pd.DataFrame(new_meme_data)
            
            # Prepare features and targets
            X_new = []
            y_new = []
            
            for _, row in df_new.iterrows():
                features = self._prepare_features(row.to_dict())
                if features:
                    X_new.append(features)
                    # Use actual upvotes/engagement as virality score
                    actual_score = min(100, max(0, row.get('upvotes', 0) / 10))
                    y_new.append(actual_score)
            
            if len(X_new) < 5:
                return
            
            # Combine with existing sample data
            df_original = self._create_sample_dataset()
            X_original = df_original[self.feature_names].values
            y_original = df_original['virality_score'].values
            
            # Scale all data
            X_combined = np.vstack([X_original, np.array(X_new)])
            y_combined = np.hstack([y_original, np.array(y_new)])
            
            X_combined_scaled = self.scaler.fit_transform(X_combined)
            
            # Retrain model
            self.model.fit(X_combined_scaled, y_combined)
            
            # Save updated model
            self._save_model()
            
            logger.info(f"Model retrained with {len(new_meme_data)} new data points")
            
        except Exception as e:
            logger.error(f"Error retraining model: {e}")