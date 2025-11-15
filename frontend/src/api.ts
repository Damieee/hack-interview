import type {
  InterviewResponse,
  ContextFields,
  ImageAnswerResponse,
  HistoryEntry,
} from "./types";

// Prefer explicit VITE_API_URL (set via .env during dev or Docker build). When the
// frontend is served by the backend in production, fall back to the current origin.
const API_URL =
  import.meta.env.VITE_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");

const SESSION_KEY = "interview-assistant-session";
const SESSION_OVERRIDE = import.meta.env.VITE_SESSION_ID;

function ensureSessionId(): string {
  if (SESSION_OVERRIDE) {
    return SESSION_OVERRIDE;
  }
  if (typeof window === "undefined") {
    return "server";
  }
  try {
    const storage = window.localStorage;
    let sessionId = storage.getItem(SESSION_KEY);
    if (!sessionId) {
      const fallback = Math.random().toString(36).slice(2);
      sessionId =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : fallback;
      storage.setItem(SESSION_KEY, sessionId);
    }
    return sessionId;
  } catch {
    return "server";
  }
}

type SubmitArgs = ContextFields & {
  audioBlob: Blob;
  position: string;
  model: string;
};

export async function submitInterview({
  audioBlob,
  position,
  model,
  jobDescription,
  companyInfo,
  aboutYou,
  resume,
}: SubmitArgs): Promise<InterviewResponse> {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.webm");
  formData.append("position", position);
  formData.append("model", model);
  formData.append("job_description", jobDescription);
  formData.append("company_info", companyInfo);
  formData.append("about_you", aboutYou);
  formData.append("resume", resume);

  const response = await fetch(`${API_URL}/api/interview`, {
    method: "POST",
    body: formData,
    headers: {
      "X-Session-Id": ensureSessionId(),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      `API error (${response.status}): ${message || "Unable to process audio"}`
    );
  }

  return (await response.json()) as InterviewResponse;
}

type ImageQuestionArgs = {
  image: Blob;
  prompt: string;
  options: string;
  model?: string;
};

export async function submitImageQuestion({
  image,
  prompt,
  options,
  model,
}: ImageQuestionArgs): Promise<ImageAnswerResponse> {
  const formData = new FormData();
  formData.append("image", image, "question.jpg");
  formData.append("prompt", prompt);
  formData.append("options", options);
  if (model) {
    formData.append("model", model);
  }

  const response = await fetch(`${API_URL}/api/image-question`, {
    method: "POST",
    body: formData,
    headers: {
      "X-Session-Id": ensureSessionId(),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      `Vision API error (${response.status}): ${
        message || "Unable to analyze image"
      }`
    );
  }

  return (await response.json()) as ImageAnswerResponse;
}

export async function fetchHistory(): Promise<HistoryEntry[]> {
  const response = await fetch(`${API_URL}/api/history`, {
    headers: {
      "X-Session-Id": ensureSessionId(),
    },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      `History API error (${response.status}): ${
        message || "Unable to load saved answers"
      }`
    );
  }
  return (await response.json()) as HistoryEntry[];
}
