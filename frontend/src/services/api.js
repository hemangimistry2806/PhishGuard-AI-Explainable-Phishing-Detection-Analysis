const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 25000;

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(formatApiError(body.detail, response.statusText, response.status));
    }

    return response.json();
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The request timed out. Confirm the backend is running and try again.");
    }
    if (error instanceof TypeError) {
      throw new Error("Unable to connect to the PhishGuard AI backend.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function formatApiError(detail, fallback, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg || "Request validation failed.").join(" ");
  }
  return fallback || `Request failed with status ${status}.`;
}

export const api = {
  baseUrl: API_BASE_URL,
  predict(features) {
    return request("/predict/", {
      method: "POST",
      body: JSON.stringify({ features }),
    });
  },
  explain(url, features) {
    return request("/explain/", {
      method: "POST",
      body: JSON.stringify({ url, features }),
    });
  },
  /**
   * Analyze any raw URL end-to-end.
   * The backend extracts features by fetching the page, then runs XGBoost + SHAP.
   * Works for arbitrary URLs, not only dataset benchmark samples.
   * @param {string} url - The URL to analyze
   * @param {boolean} includeExplanation - Whether to include SHAP/LLM explanation
   */
  analyzeUrl(url, includeExplanation = true) {
    return request("/analyze/", {
      method: "POST",
      body: JSON.stringify({ url, include_explanation: includeExplanation }),
    });
  },
  submitFeedback(url, model_prediction, user_verdict, comment = "") {
    return request("/feedback/", {
      method: "POST",
      body: JSON.stringify({ url, model_prediction, user_verdict, comment }),
    });
  },
  getFeedbackStats() {
    return request("/feedback/stats");
  },
};

