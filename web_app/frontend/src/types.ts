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
