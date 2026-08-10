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

export const STATUS_LABELS: Record<string, string> = {
  created: "Starting up...",
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
