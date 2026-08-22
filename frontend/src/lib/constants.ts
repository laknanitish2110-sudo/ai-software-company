export const AGENT_CONFIG: Record<
  string,
  { label: string; icon: string; color: string; description: string }
> = {
  ceo: {
    label: "CEO",
    icon: "👨‍💼",
    color: "#6366f1",
    description: "Project Manager — plans, delegates, coordinates",
  },
  business_analyst: {
    label: "Business Analyst",
    icon: "📋",
    color: "#10b981",
    description: "Requirements, user stories, scope analysis",
  },
  researcher: {
    label: "Researcher",
    icon: "🔍",
    color: "#f59e0b",
    description: "Competitors, APIs, best practices",
  },
  architect: {
    label: "Solution Architect",
    icon: "🏗️",
    color: "#8b5cf6",
    description: "Tech stack, architecture, database design",
  },
  engineer: {
    label: "Software Engineer",
    icon: "💻",
    color: "#ef4444",
    description: "Production code, APIs, deployment",
  },
  ppt: {
    label: "Presentation Expert",
    icon: "📊",
    color: "#06b6d4",
    description: "Slides, README, pitch, documentation",
  },
};

export const PIPELINE_ORDER = [
  "ceo",
  "business_analyst",
  "researcher",
  "architect",
  "engineer",
  "ppt",
];

export const MODEL_LABELS: Record<string, { model: string; provider: string; providerColor: string }> = {
  ceo: { model: "Gemini Flash", provider: "Google", providerColor: "#4285f4" },
  business_analyst: { model: "Claude Sonnet", provider: "Anthropic", providerColor: "#d4a27f" },
  researcher: { model: "Gemini Flash", provider: "Google", providerColor: "#4285f4" },
  architect: { model: "Claude Sonnet", provider: "Anthropic", providerColor: "#d4a27f" },
  engineer: { model: "GPT-4o", provider: "OpenAI", providerColor: "#10a37f" },
  ppt: { model: "Gemini Flash", provider: "Google", providerColor: "#4285f4" },
};

export const STATUS_LABELS: Record<string, string> = {
  created: "CEO is analyzing...",
  ba_working: "Business Analyst is working",
  ba_review: "Review: Business Analysis",
  research_working: "Researcher is working",
  research_review: "Review: Research",
  architect_working: "Architect is working",
  architect_review: "Review: Architecture",
  engineer_working: "Engineer is working",
  engineer_review: "Review: Implementation",
  ppt_working: "Presentation Expert is working",
  completed: "Project Complete",
  paused: "Paused",
};
