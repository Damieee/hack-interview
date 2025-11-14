import { useCallback, useMemo, useState } from "react";
import { ContextPanel } from "./components/ContextPanel";
import { useRecorder } from "./hooks/useRecorder";
import { submitImageQuestion, submitInterview } from "./api";
import type {
  ContextFields,
  InterviewResponse,
  ImageAnswerResponse,
} from "./types";

const MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"];

const initialContext: ContextFields = {
  jobDescription: "",
  companyInfo: "",
  aboutYou: "",
  resume: "",
};

function App() {
  const [position, setPosition] = useState("Python Developer");
  const [model, setModel] = useState(MODELS[0]);
  const [contextFields, setContextFields] = useState<ContextFields>(
    initialContext,
  );
  const [status, setStatus] = useState<string>("Idle");
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<InterviewResponse | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [imagePrompt, setImagePrompt] = useState("");
  const [imageOptions, setImageOptions] = useState("");
  const [imageAnswer, setImageAnswer] = useState<ImageAnswerResponse | null>(
    null,
  );
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);

  const contextSummary = useMemo(() => {
    const entries = Object.entries(contextFields)
      .filter(([, value]) => value.trim().length)
      .map(([key, value]) => `${key}: ${value.trim()}`);
    return entries.join("\n\n");
  }, [contextFields]);

  const handleSegment = useCallback(
    async (blob: Blob) => {
      setStatus("Uploading audio…");
      setError(null);
      setIsSubmitting(true);
      try {
        const response = await submitInterview({
          audioBlob: blob,
          position,
          model,
          ...contextFields,
        });
        setLastResponse(response);
        setStatus("Complete");
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Unable to process audio.",
        );
        setStatus("Error");
      } finally {
        setIsSubmitting(false);
      }
    },
    [contextFields, model, position],
  );

  const { isRecording, start, stop, error: recorderError } = useRecorder({
    onSegment: handleSegment,
  });

  const handleImageUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      setImageLoading(true);
      setImageError(null);
      setImageAnswer(null);
      try {
        const response = await submitImageQuestion({
          image: file,
          prompt: imagePrompt,
          options: imageOptions,
          model,
        });
        setImageAnswer(response);
      } catch (err) {
        setImageError(
          err instanceof Error ? err.message : "Unable to analyze image.",
        );
      } finally {
        setImageLoading(false);
        event.target.value = "";
      }
    },
    [imagePrompt, imageOptions, model],
  );

  return (
    <div className="app-shell">
      <ContextPanel
        values={contextFields}
        onChange={(fields) =>
          setContextFields((prev) => ({ ...prev, ...fields }))
        }
      />

      <div className="panel main-panel">
        <header>
          <h1>AI Interview Assistant</h1>
          <p className="status">
            {isRecording
              ? "Listening… press stop when you finish speaking."
              : status}
          </p>
        </header>

        <section>
          <label>Position / Role</label>
          <input
            value={position}
            onChange={(event) => setPosition(event.target.value)}
          />
        </section>

        <section>
          <label>Model</label>
          <select
            value={model}
            onChange={(event) => setModel(event.target.value)}
          >
            {MODELS.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </select>
        </section>

        <section style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button onClick={start} disabled={isRecording}>
            🎙️ Start Recording
          </button>
          <button className="secondary" onClick={stop} disabled={!isRecording}>
            ⏹ Stop &amp; Transcribe
          </button>
        </section>

        {(error || recorderError) && (
          <p className="error">{error ?? recorderError}</p>
        )}

        <section className="panel">
          <h3>Transcript</h3>
          <div className="transcript">
            {lastResponse?.transcript ?? "No transcript yet."}
          </div>
        </section>

        <section className="answers-grid">
          <div className="panel">
            <h3>Quick Answer</h3>
            <p>{lastResponse?.quick_answer ?? "Awaiting input…"}</p>
          </div>
          <div className="panel">
            <h3>Full Answer</h3>
            <p>{lastResponse?.full_answer ?? "Awaiting input…"}</p>
          </div>
        </section>

        <section className="panel">
          <h3>Context Summary</h3>
          <pre className="transcript">
            {contextSummary || "No context supplied yet."}
          </pre>
        </section>

        <section className="panel">
          <h3>Camera Question (mobile friendly)</h3>
          <p>
            Open this site on your phone, tap “Choose file”, and take a photo of
            the question. The model will analyze the screenshot/photo and pick
            the best option.
          </p>
          <label>Additional Prompt (optional)</label>
          <input
            placeholder="e.g. Choose the correct answer"
            value={imagePrompt}
            onChange={(event) => setImagePrompt(event.target.value)}
          />
          <label>Options (newline or semicolon separated)</label>
          <textarea
            rows={3}
            placeholder={"Option A) …\nOption B) …"}
            value={imageOptions}
            onChange={(event) => setImageOptions(event.target.value)}
          />
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleImageUpload}
          />
          {imageLoading && <p className="status">Analyzing image…</p>}
          {imageError && <p className="error">{imageError}</p>}
          {imageAnswer && (
            <div className="panel" style={{ marginTop: "0.75rem" }}>
              <h4>Vision Answer</h4>
              {imageAnswer.selected_option && (
                <p>
                  <strong>Selected:</strong> {imageAnswer.selected_option}
                </p>
              )}
              <p>{imageAnswer.answer}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
