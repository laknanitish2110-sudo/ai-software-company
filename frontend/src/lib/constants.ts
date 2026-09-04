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

export const ROUTE_CONFIG: Record<string, {
  name: string;
  description: string;
  agents: string[];
  icon: string;
  estimatedMinutes: number;
}> = {
  quick_build: {
    name: "Quick Build",
    description: "Fast single-feature app — skip research and analysis",
    agents: ["ceo", "engineer"],
    icon: "⚡",
    estimatedMinutes: 3,
  },
  standard: {
    name: "Standard",
    description: "Requirements, architecture, and code",
    agents: ["ceo", "business_analyst", "architect", "engineer"],
    icon: "🔧",
    estimatedMinutes: 10,
  },
  full: {
    name: "Full Pipeline",
    description: "Complete analysis with research, code, and presentation",
    agents: ["ceo", "business_analyst", "researcher", "architect", "engineer", "ppt"],
    icon: "🏢",
    estimatedMinutes: 20,
  },
  research: {
    name: "Research Only",
    description: "Market analysis and feasibility study — no code",
    agents: ["ceo", "business_analyst", "researcher"],
    icon: "🔍",
    estimatedMinutes: 8,
  },
  report: {
    name: "Report",
    description: "Document or pitch deck — no code generation",
    agents: ["ceo", "business_analyst", "ppt"],
    icon: "📊",
    estimatedMinutes: 6,
  },
};

const SIMPLE_KW = ["calculator","todo","to-do","timer","counter","converter","stopwatch","clock","quiz","flashcard","tic-tac-toe","hangman","snake game","pong","memory game","dice","coin flip","bmi","tip calculator","unit converter","color picker","notepad","password generator","random quote","weather app","hello world"];
const QUICK_KW = ["landing page","portfolio","blog","static site","homepage","coming soon","single page","one page","simple app","basic app","prototype","mockup","demo"];
const RESEARCH_KW = ["analyze","analysis","research","compare","comparison","market","feasibility","study","survey","benchmark","evaluate","assessment","investigate","explore options","landscape"];
const COMPLEX_KW = ["saas","platform","multi-tenant","billing","subscription","authentication","authorization","real-time","microservice","distributed","scalable","enterprise","marketplace","e-commerce","payment","stripe","oauth","sso","api gateway","kubernetes","docker"];
const REPORT_KW = ["pitch","presentation","proposal","report","document","slide","deck","whitepaper","brief","memo","business plan"];

export function classifyTask(problemStatement: string): string {
  const text = problemStatement.toLowerCase().trim();
  const words = text.split(/\s+/).length;
  const scores: Record<string, number> = { quick_build: 0, standard: 0, full: 0, research: 0, report: 0 };

  for (const kw of SIMPLE_KW) if (text.includes(kw)) scores.quick_build += 3;
  for (const kw of QUICK_KW) if (text.includes(kw)) scores.quick_build += 2;
  for (const kw of RESEARCH_KW) if (text.includes(kw)) scores.research += 3;
  for (const kw of COMPLEX_KW) if (text.includes(kw)) scores.full += 3;
  for (const kw of REPORT_KW) if (text.includes(kw)) scores.report += 3;

  if (words < 15) scores.quick_build += 2;
  else if (words < 40) scores.standard += 1;
  else scores.full += 2;

  const maxScore = Math.max(...Object.values(scores));
  if (maxScore === 0) return "full";

  let suggested = Object.entries(scores).reduce((a, b) => (b[1] > a[1] ? b : a))[0];

  if (suggested === "research" || suggested === "report") {
    const codeSignals = ["build", "create", "develop", "implement", "code", "app", "website", "api", "software"];
    if (codeSignals.some((kw) => text.includes(kw)) && scores[suggested] < 6) {
      suggested = "standard";
    }
  }

  return suggested;
}

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
