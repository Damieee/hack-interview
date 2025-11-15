export type InterviewResponse = {
  transcript: string;
  quick_answer: string;
  full_answer: string;
};

export type ContextFields = {
  jobDescription: string;
  companyInfo: string;
  aboutYou: string;
  resume: string;
};

export type ImageAnswerResponse = {
  answer: string;
  selected_option?: string | null;
};

export type HistoryEntry = {
  id: string;
  entry_type: "interview" | "vision";
  created_at: string;
  transcript?: string | null;
  quick_answer?: string | null;
  full_answer?: string | null;
  answer?: string | null;
  selected_option?: string | null;
  prompt?: string | null;
  options?: string[] | null;
  position?: string | null;
  model?: string | null;
};
