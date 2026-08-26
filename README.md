# PhishGuard AI

Explainable Phishing Detection & Analysis

## Overview
PhishGuard AI is an AI-powered web application that detects phishing URLs, predicts risk scores using machine learning, and provides explainable threat analysis using SHAP and LLMs.

## Technologies
- Machine Learning
- Explainable AI (SHAP)
- Large Language Models (Gemini)
- FastAPI
- React

## API Contract (Backend)

**Current inference mode:**
Pre-extracted PhiUSIIL 50-feature vector. Endpoints (`/predict` and `/explain`) strictly require a 50-element numeric array.

**Raw URL feature extraction:**
*Not implemented.* Generating the exact 50 features from a raw URL is not safely reproducible at this stage because the original feature-generation methodology and statistical resources (such as the TLD legitimate probability matrices) used by the dataset authors are unavailable in this repository. 
The backend handles ML orchestration, explanation, and model evaluation via pre-extracted data.
