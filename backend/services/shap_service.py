import shap
import numpy as np


class SHAPService:

    def __init__(self, model):
        # Prediction service se trained model receive kar rahe hain
        self.model = model

        # XGBoost model ke liye TreeExplainer create kar rahe hain
        self.explainer = shap.TreeExplainer(self.model)

    def explain(self, features, feature_names):
        """
        Given features ke liye SHAP explanation generate karta hai.

        Parameters:
            features: URL se extracted features
            feature_names: Features ke corresponding names

        Returns:
            Important features aur unki SHAP values
        """

        # Features ko NumPy array mein convert karke 2D format mein rakh rahe hain
        X = np.array(features).reshape(1, -1)

        # Model prediction ke decision ko SHAP values mein explain kar rahe hain
        shap_values = self.explainer.shap_values(X)

        # Single prediction ke liye SHAP values extract kar rahe hain
        values = shap_values[0]

        # Feature name aur SHAP value ko pair kar rahe hain
        feature_importance = []

        for name, value in zip(feature_names, values):
            feature_importance.append({
                "feature": name,
                "shap_value": float(value)
            })

        # Sabse influential features ko pehle rakh rahe hain
        feature_importance.sort(
            key=lambda x: abs(x["shap_value"]),
            reverse=True
        )

        return feature_importance