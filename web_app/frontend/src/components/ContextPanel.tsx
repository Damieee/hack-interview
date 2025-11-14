import type { ContextFields } from "../types";

type Props = {
  values: ContextFields;
  onChange: (fields: Partial<ContextFields>) => void;
};

const sections: {
  key: keyof ContextFields;
  label: string;
  rows: number;
}[] = [
  { key: "jobDescription", label: "Job Description", rows: 5 },
  { key: "companyInfo", label: "Company / Product", rows: 4 },
  { key: "aboutYou", label: "About You", rows: 4 },
  { key: "resume", label: "Resume Highlights", rows: 6 },
];

export function ContextPanel({ values, onChange }: Props) {
  const handleFileLoad = async (
    key: keyof ContextFields,
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    onChange({ [key]: text });
    event.target.value = "";
  };

  return (
    <div className="panel context-panel">
      <h2>Interview Context</h2>
      <p>
        Paste details about the role, company, and yourself. The model will use
        this information to craft tailored answers.
      </p>

      {sections.map(({ key, label, rows }) => (
        <section key={key} style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <label>{label}</label>
            <label className="secondary" style={{ fontSize: "0.8rem" }}>
              <input
                type="file"
                accept=".txt"
                style={{ display: "none" }}
                onChange={(event) => handleFileLoad(key, event)}
              />
              <span style={{ cursor: "pointer", color: "#38bdf8" }}>
                Load file
              </span>
            </label>
          </div>
          <textarea
            rows={rows}
            value={values[key]}
            onChange={(event) => onChange({ [key]: event.target.value })}
          />
        </section>
      ))}
    </div>
  );
}

