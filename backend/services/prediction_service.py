import os
import pickle
import numpy as np


class PredictionService:

    def __init__(self):
        # Project root directory ka path nikal rahe hain
        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        # Trained XGBoost model path with MODEL_PATH environment variable support
        env_model_path = os.getenv("MODEL_PATH")
        if env_model_path and os.path.exists(env_model_path):
            model_path = env_model_path
        else:
            model_path = os.path.join(
                base_dir,
                "ml",
                "models",
                "xgboost_model.pkl"
            )

        # Saved XGBoost model ko load kar rahe hain
        with open(model_path, "rb") as file:
            self.model = pickle.load(file)

    def predict(self, features):
        """
        Given features ke basis par phishing prediction karta hai.

        Parameters:
            features: URL se extracted features ki list

        Returns:
            Prediction aur dono classes ki probability
        """

        # Features ko NumPy array mein convert karke
        # model ke liye 2D format mein reshape kar rahe hain
        X = np.array(features).reshape(1, -1)

        # Model se prediction nikal rahe hain
        prediction = self.model.predict(X)[0]

        # Phishing aur legitimate dono ki probability nikal rahe hain
        probabilities = self.model.predict_proba(X)[0]

        # PhiUSIIL dataset and trained XGBoost model:
        # Class 0 = Phishing, Class 1 = Legitimate (model.classes_ == [0, 1])
        phishing_probability = float(probabilities[0])
        legitimate_probability = float(probabilities[1])

        # Prediction ko human-readable label mein convert kar rahe hain:
        # 1 = Legitimate, 0 = Phishing
        if prediction == 1:
            label = "Legitimate"
        else:
            label = "Phishing"

        # Final result dictionary ke form mein return kar rahe hain
        return {
            "prediction": int(prediction),
            "label": label,
            "phishing_probability": phishing_probability,
            "legitimate_probability": legitimate_probability
        }