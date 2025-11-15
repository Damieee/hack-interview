import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { ContextPanel } from "./components/ContextPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { useRecorder } from "./hooks/useRecorder";
import { fetchHistory, submitImageQuestion, submitInterview } from "./api";
import type {
  ContextFields,
  InterviewResponse,
  ImageAnswerResponse,
  HistoryEntry,
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
  const [screenshotSupported, setScreenshotSupported] = useState<boolean>(
    !!navigator.mediaDevices?.getDisplayMedia,
  );
  const [cameraSupported] = useState<boolean>(
    !!navigator.mediaDevices?.getUserMedia,
  );
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraLoopActive, setCameraLoopActive] = useState(false);
  const [sidePanelView, setSidePanelView] = useState<"documents" | "answers">(
    "documents",
  );
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const cameraLoopRef = useRef(false);

  const contextSummary = useMemo(() => {
    const entries = Object.entries(contextFields)
      .filter(([, value]) => value.trim().length)
      .map(([key, value]) => `${key}: ${value.trim()}`);
    return entries.join("\n\n");
  }, [contextFields]);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const entries = await fetchHistory();
      setHistoryEntries(entries);
    } catch (err) {
      setHistoryError(
        err instanceof Error ? err.message : "Unable to load saved answers.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

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
        await refreshHistory();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Unable to process audio.",
        );
        setStatus("Error");
      } finally {
        setIsSubmitting(false);
      }
    },
    [contextFields, model, position, refreshHistory],
  );

  const { isRecording, start, stop, error: recorderError } = useRecorder({
    onSegment: handleSegment,
  });

  const handleImageUpload = useCallback(
    async (file: Blob | File | null) => {
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
        await refreshHistory();
      } catch (err) {
        setImageError(
          err instanceof Error ? err.message : "Unable to analyze image.",
        );
      } finally {
        setImageLoading(false);
      }
    },
    [imagePrompt, imageOptions, model, refreshHistory],
  );

  const requestScreenshot = useCallback(async () => {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setScreenshotSupported(false);
      setImageError("Screen capture is not supported in this browser.");
      return;
    }
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "monitor" },
      });
      const track = stream.getVideoTracks()[0];
      const video = document.createElement("video");
      video.srcObject = stream;
      await video.play();

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext("2d");
      context?.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/png"),
      );
      track.stop();
      if (blob) {
        await handleImageUpload(blob);
      }
    } catch (err) {
      setImageError(
        err instanceof Error
          ? err.message
          : "Unable to capture screen. Please allow permissions.",
      );
    } finally {
      stream?.getTracks().forEach((t) => t.stop());
    }
  }, [handleImageUpload]);

  useEffect(() => {
    cameraLoopRef.current = cameraLoopActive;
  }, [cameraLoopActive]);

  const stopCamera = useCallback(() => {
    cameraStream?.getTracks().forEach((track) => track.stop());
    setCameraStream(null);
    setCameraActive(false);
  }, [cameraStream]);

  useEffect(() => {
    if (cameraStream && videoRef.current) {
      videoRef.current.srcObject = cameraStream;
      videoRef.current.play().catch(() => {
        setImageError("Unable to start camera preview.");
        stopCamera();
      });
    }
  }, [cameraStream, stopCamera]);

  const requestCameraPreview = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setImageError("Camera capture is not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      setCameraStream(stream);
      setCameraActive(true);
    } catch (err) {
      setImageError(
        err instanceof Error
          ? err.message
          : "Unable to access camera. Please allow permissions.",
      );
    }
  }, []);

  const startCameraLoop = useCallback(() => {
    setCameraLoopActive(true);
    void requestCameraPreview();
  }, [requestCameraPreview]);

  const cancelCameraLoop = useCallback(() => {
    setCameraLoopActive(false);
    stopCamera();
  }, [stopCamera]);

  const snapPhoto = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const context = canvas.getContext("2d");
    context?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9),
    );
    stopCamera();
    if (blob) {
      await handleImageUpload(blob);
    }
    if (cameraLoopRef.current) {
      await requestCameraPreview();
    }
  }, [handleImageUpload, requestCameraPreview, stopCamera]);

  return (
    <div className="app-shell">
      <div className="panel context-panel">
        <div className="side-panel-tabs">
          <button
            type="button"
            className={sidePanelView === "documents" ? "active" : ""}
            onClick={() => setSidePanelView("documents")}
          >
            Documents
          </button>
          <button
            type="button"
            className={sidePanelView === "answers" ? "active" : ""}
            onClick={() => setSidePanelView("answers")}
          >
            Answers
          </button>
        </div>
        {sidePanelView === "documents" ? (
          <ContextPanel
            values={contextFields}
            onChange={(fields) =>
              setContextFields((prev) => ({ ...prev, ...fields }))
            }
          />
        ) : (
          <HistoryPanel
            entries={historyEntries}
            loading={historyLoading}
            error={historyError}
            onRefresh={refreshHistory}
          />
        )}
      </div>

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
          <div
            style={{
              display: "flex",
              gap: "0.75rem",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <label className="upload-button">
              <input
                type="file"
                accept="image/*"
                capture="environment"
                style={{ display: "none" }}
                onChange={(event) => handleImageUpload(event.target.files?.[0] ?? null)}
              />
              📷 Choose Photo
            </label>
            <button
              type="button"
              className="secondary"
              disabled={!screenshotSupported || imageLoading}
              onClick={requestScreenshot}
            >
              🖥️ Capture Screen
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!cameraSupported || imageLoading}
              onClick={startCameraLoop}
            >
              📸 Use Webcam
            </button>
          </div>
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
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {imageAnswer.answer}
              </ReactMarkdown>
            </div>
          )}
        </section>
      </div>

      {cameraActive && (
        <div className="camera-overlay">
          <div className="camera-panel">
            <video ref={videoRef} autoPlay playsInline muted />
            <div className="camera-controls">
              <button onClick={snapPhoto} disabled={imageLoading}>
                📸 Snap Photo
              </button>
              <button className="secondary" onClick={cancelCameraLoop}>
                ✖ Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
