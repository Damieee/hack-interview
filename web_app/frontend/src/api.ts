import type { InterviewResponse, ContextFields } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      `API error (${response.status}): ${message || "Unable to process audio"}`
    );
  }

  return (await response.json()) as InterviewResponse;
}

