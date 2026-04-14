export interface BuilderNavItem {
  id: "search" | "plugins" | "automations";
  label: string;
}

export interface BuilderThread {
  id: string;
  title: string;
  updatedAt: string;
  rawUpdatedAt?: string;
}

export interface BuilderThreadGroup {
  id: string;
  label: string;
  path: string;
  threads: BuilderThread[];
}

export interface BuilderConversation {
  id: string;
  title: string;
  subtitle: string;
  groupId: string;
  updatedAt: string;
}

export interface BuilderMessage {
  id: string;
  role: "assistant" | "user";
  text: string;
  isStreaming?: boolean;
  reasoningLines?: string[];
  typingText?: string;
}

export interface BuilderPromptSuggestion {
  id: string;
  title: string;
  description: string;
}

export const builderNavItems: BuilderNavItem[] = [
  { id: "search", label: "Search" },
  { id: "plugins", label: "Plugins" },
  { id: "automations", label: "Automations" },
];

export const builderThreadGroups: BuilderThreadGroup[] = [
  {
    id: "secure-scan-studio-main",
    label: "secure-scan-studio-main",
    path: "D:\\workspace\\secure-scan-studio-main",
    threads: [
      { id: "frontend-architecture", title: "Restructure frontend architecture", updatedAt: "1h" },
      { id: "security-scan-ui", title: "Refine Security Analyst workspace", updatedAt: "43m" },
      { id: "sidebar-polish", title: "Tighten sidebar spacing and overflow", updatedAt: "11h" },
    ],
  },
  {
    id: "main",
    label: "main",
    path: "D:\\workspace\\main",
    threads: [{ id: "responsive-chart", title: "Responsive chart conversion", updatedAt: "2h" }],
  },
  {
    id: "workspace",
    label: "workspace",
    path: "D:\\workspace\\workspace",
    threads: [
      { id: "clarify-request", title: "Clarify vague request", updatedAt: "1mo" },
      { id: "simple-hello", title: "hey", updatedAt: "1mo" },
      { id: "health-checks", title: "Stop unnecessary health checks", updatedAt: "1mo" },
      { id: "campaign-copy", title: "Convert product notes into launch copy", updatedAt: "4h" },
      { id: "copy-cleanup", title: "Tighten launch copy structure", updatedAt: "6d" },
    ],
  },
];

export const builderConversations: BuilderConversation[] = [
  {
    id: "frontend-architecture",
    title: "Restructure frontend architecture",
    subtitle: "secure-scan-studio-main",
    groupId: "secure-scan-studio-main",
    updatedAt: "1h",
  },
  {
    id: "security-scan-ui",
    title: "Refine Security Analyst workspace",
    subtitle: "secure-scan-studio-main",
    groupId: "secure-scan-studio-main",
    updatedAt: "43m",
  },
  {
    id: "sidebar-polish",
    title: "Tighten sidebar spacing and overflow",
    subtitle: "secure-scan-studio-main",
    groupId: "secure-scan-studio-main",
    updatedAt: "11h",
  },
  {
    id: "responsive-chart",
    title: "Responsive chart conversion",
    subtitle: "main",
    groupId: "main",
    updatedAt: "2h",
  },
  {
    id: "clarify-request",
    title: "Clarify vague request",
    subtitle: "workspace",
    groupId: "workspace",
    updatedAt: "1mo",
  },
  {
    id: "simple-hello",
    title: "hey",
    subtitle: "workspace",
    groupId: "workspace",
    updatedAt: "1mo",
  },
  {
    id: "health-checks",
    title: "Stop unnecessary health checks",
    subtitle: "workspace",
    groupId: "workspace",
    updatedAt: "1mo",
  },
  {
    id: "campaign-copy",
    title: "Convert product notes into launch copy",
    subtitle: "workspace",
    groupId: "workspace",
    updatedAt: "4h",
  },
  {
    id: "copy-cleanup",
    title: "Tighten launch copy structure",
    subtitle: "workspace",
    groupId: "workspace",
    updatedAt: "6d",
  },
];

export const builderMessages: Record<string, BuilderMessage[]> = {
  "frontend-architecture": [
    {
      id: "m1",
      role: "assistant",
      text: "I reviewed the current frontend structure. The main issue is mixed responsibilities across the page shell, workspace switch, and builder-specific UI.",
    },
    {
      id: "m2",
      role: "user",
      text: "Turn that into an implementation plan.",
    },
    {
      id: "m3",
      role: "assistant",
      text: "Plan: stabilize the workspace switch at the page level, isolate builder navigation and chat into a dedicated feature, then keep the brand shell fixed while only swapping content beneath the mode switch.",
    },
  ],
  "security-scan-ui": [
    {
      id: "m4",
      role: "assistant",
      text: "The Security Analyst workspace already has a solid visual language. The next improvement is to align the builder workspace to the same spacing, typography, and shell behavior.",
    },
  ],
  "sidebar-polish": [
    {
      id: "m5",
      role: "assistant",
      text: "The cleanest fix is to keep the sidebar shell stable and only animate lightweight content changes. That avoids the jumpiness you were seeing before.",
    },
  ],
  "responsive-chart": [
    {
      id: "m6",
      role: "assistant",
      text: "Start with chart domain types, extract a focused rendering widget, then attach it to the dashboard with one container component.",
    },
  ],
  "campaign-copy": [
    {
      id: "m7",
      role: "assistant",
      text: "I can turn these notes into launch copy, an internal brief, and a concise product announcement draft.",
    },
  ],
  "clarify-request": [
    {
      id: "m8",
      role: "assistant",
      text: "I can help shape the request. Tell me the goal, the target file or screen, and the expected outcome.",
    },
  ],
  "simple-hello": [
    {
      id: "m9",
      role: "assistant",
      text: "Hi. I am ready to help with planning, coding, debugging, or drafting inside this workspace.",
    },
  ],
  "health-checks": [
    {
      id: "m10",
      role: "assistant",
      text: "The current health checks are too noisy. We should keep readiness strict, move expensive checks to diagnostics, and shorten the failure path.",
    },
  ],
  "copy-cleanup": [
    {
      id: "m11",
      role: "assistant",
      text: "The launch copy needs a stronger hierarchy: product value first, proof second, call to action last.",
    },
  ],
};

export const builderPromptSuggestions: BuilderPromptSuggestion[] = [
  {
    id: "snake-game",
    title: "Build a classic Snake game in this repo",
    description: "Scaffold the UI, gameplay loop, and keyboard controls in one pass.",
  },
  {
    id: "summarize-app",
    title: "Create a one-page summary for this app",
    description: "Produce a clean artifact with product scope, architecture, and next steps.",
  },
  {
    id: "plan-feature",
    title: "Create a plan for the next feature",
    description: "Break work into implementation steps, risks, and verification points.",
  },
];
