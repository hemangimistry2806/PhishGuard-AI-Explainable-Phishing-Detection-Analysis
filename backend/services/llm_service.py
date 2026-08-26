import os
from openai import OpenAI


class LLMService:

    def __init__(self):
        # Environment variable se API key le rahe hain
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        # API key missing hai toh error raise kar rahe hain
        if not openrouter_key and not openai_key:
            raise ValueError("Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set")

        if openrouter_key:
            self.client = OpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            self.client = OpenAI(api_key=openai_key)

        # Environment variable se model name le rahe hain
        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-4o-mini"
        )

    def generate_explanation(self, url, prediction, shap_features):

        # Top important SHAP features select kar rahe hain
        important_features = shap_features[:10]

        # SHAP information ko readable format mein convert kar rahe hain
        feature_text = "\n".join(
            f"- {item['feature']}: {item['shap_value']:.4f}"
            for item in important_features
        )

        # LLM ke liye explanation prompt prepare kar rahe hain
        prompt = f"""
You are an explainable phishing detection assistant.

URL:
{url}

Machine Learning Prediction:
{prediction}

Important SHAP Features:
{feature_text}

Explain why the machine learning model made this prediction.

Rules:
- Do not change the model prediction.
- Use only the provided SHAP evidence.
- Do not invent features or evidence.
- Explain the result in simple language.
"""

        # LLM se explanation generate kar rahe hain
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2
        )

        # Generated explanation return kar rahe hain
        return response.choices[0].message.content