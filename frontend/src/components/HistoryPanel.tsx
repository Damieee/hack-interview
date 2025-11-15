import type { HistoryEntry } from "../types";

type Props = {
  entries: HistoryEntry[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
};

const labels: Record<HistoryEntry["entry_type"], string> = {
  interview: "Audio Answer",
  vision: "Image Answer",
};

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function HistoryPanel({ entries, loading, error, onRefresh }: Props) {
  return (
    <>
      <div className="history-header">
        <div>
          <h2>Saved Answers</h2>
          <p style={{ marginTop: "0.25rem", color: "#cbd5f5" }}>
            Stored securely in Redis for 24 hours.
          </p>
        </div>
        <button className="secondary" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && <p className="status">Fetching history…</p>}
      {!loading && entries.length === 0 && <p>No answers saved yet.</p>}
      <div className="history-list">
        {entries.map((entry) => (
          <article key={entry.id} className="history-entry">
            <div className="history-entry__meta">
              <span className="history-entry__badge">{labels[entry.entry_type]}</span>
              <small>{formatTimestamp(entry.created_at)}</small>
            </div>
            {entry.entry_type === "vision" ? (
              <>
                {entry.selected_option && (
                  <p className="history-entry__selected">
                    <strong>{entry.selected_option}</strong>
                  </p>
                )}
                <p className="history-entry__content">{entry.answer}</p>
                {entry.prompt && (
                  <p className="history-entry__prompt">
                    <strong>Prompt:</strong> {entry.prompt}
                  </p>
                )}
              </>
            ) : (
              <>
                <p className="history-entry__content">{entry.quick_answer}</p>
                <details>
                  <summary>View transcript & full answer</summary>
                  <p className="history-entry__transcript">
                    <strong>Transcript:</strong> {entry.transcript}
                  </p>
                  <p className="history-entry__content">{entry.full_answer}</p>
                </details>
              </>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
