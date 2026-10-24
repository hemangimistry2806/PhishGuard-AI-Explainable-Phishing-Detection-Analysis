const API_BASE_URL = typeof import.meta.env.VITE_API_BASE_URL !== "undefined"
  ? import.meta.env.VITE_API_BASE_URL
  : "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 25000;

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
      throw new Error("Unable to connect to the PhishGuard AI backend. Ensure FastAPI server is running on port 8000.");
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
  analyzeUrl(url, includeExplanation = true) {
    return request("/analyze/", {
      method: "POST",
      body: JSON.stringify({ url, include_explanation: includeExplanation }),
    });
  },
  submitFeedback(data) {
    // Supports either an object payload or legacy positional arguments
    let body;
    if (typeof data === "string") {
      const [url, model_prediction, user_verdict, comment] = arguments;
      body = { url, model_prediction, user_verdict, comment: comment || "" };
    } else {
      body = data;
    }
    return request("/feedback/", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  getFeedbackStats() {
    return request("/feedback/stats");
  },
  listFeedback(params = {}) {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.disagreements_only) query.set("disagreements_only", "true");
    if (params.limit) query.set("limit", params.limit);
    if (params.offset) query.set("offset", params.offset);
    const qs = query.toString();
    return request(`/feedback/list${qs ? `?${qs}` : ""}`);
  },
  reviewFeedback(feedbackId, reviewData, reviewerKey) {
    return request(`/feedback/${feedbackId}/review`, {
      method: "PATCH",
      headers: { "X-Reviewer-Key": reviewerKey },
      body: JSON.stringify(reviewData),
    });
  },
  exportCandidateDataset(reviewerKey) {
    return request("/feedback/candidate-dataset", {
      headers: { "X-Reviewer-Key": reviewerKey },
    });
  },
  getModelEvaluation() {
    return request("/model/evaluation");
  },
  checkHealth() {
    return request("/");
  },
};
