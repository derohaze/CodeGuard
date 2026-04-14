import type { BuilderMessage } from "../mockBuilderAgent";
import type { BuilderComposerSettings } from "./types";

const CONTEXT_WINDOW_BUDGET_TOKENS = 24000;
const BASE_CONTEXT_TOKENS = 120;
const MESSAGE_ROLE_OVERHEAD_TOKENS = 10;
const ROLLING_SUMMARY_BASE_TOKENS = 120;
const MEMORY_RETRIEVAL_BASE_TOKENS = 110;
const ATTACHMENT_CONTEXT_TOKENS = 180;
const PLAN_MODE_TOKENS = 90;
const MAX_RECENT_MESSAGES = 10;

export interface BuilderContextUsage {
  maxTokens: number;
  percentage: number;
  usedTokens: number;
}

export interface BuilderContextMemory {
  id: string;
  memoryClass: string;
  title: string;
  content: string;
  updatedAt: string | null;
}

export interface BuilderContextState extends BuilderContextUsage {
  rollingSummary: string;
  recentMessageCount: number;
  memoryCount: number;
  memoryItems: BuilderContextMemory[];
  updatedAt: string | null;
}

interface EstimateBuilderContextUsageParams {
  composerSettings: BuilderComposerSettings;
  draft: string;
  messages: BuilderMessage[];
}

interface ResolveBuilderContextUsageParams extends EstimateBuilderContextUsageParams {
  backendContextState?: BuilderContextState | null;
}

export function estimateBuilderContextUsage({
  composerSettings,
  draft,
  messages,
}: EstimateBuilderContextUsageParams): BuilderContextUsage {
  const recentMessages = messages.slice(-MAX_RECENT_MESSAGES);
  const olderMessages = messages.slice(0, -MAX_RECENT_MESSAGES);
  const trimmedDraft = draft.trim();

  const recentMessageTokens = recentMessages.reduce(
    (sum, message) => sum + estimateTextTokens(message.text) + MESSAGE_ROLE_OVERHEAD_TOKENS,
    0,
  );
  const olderMessageTokens = olderMessages.reduce(
    (sum, message) => sum + estimateTextTokens(message.text) + MESSAGE_ROLE_OVERHEAD_TOKENS,
    0,
  );

  const rollingSummaryTokens =
    olderMessages.length > 0
      ? Math.min(640, ROLLING_SUMMARY_BASE_TOKENS + Math.round(olderMessageTokens * 0.1))
      : 0;
  const memoryRetrievalTokens =
    olderMessages.length > 0
      ? MEMORY_RETRIEVAL_BASE_TOKENS
      : 0;
  const attachmentTokens = composerSettings.attachedFiles.length * ATTACHMENT_CONTEXT_TOKENS;
  const draftTokens = estimateTextTokens(trimmedDraft);

  const usedTokens =
    BASE_CONTEXT_TOKENS +
    recentMessageTokens +
    rollingSummaryTokens +
    memoryRetrievalTokens +
    attachmentTokens +
    draftTokens +
    (composerSettings.planMode ? PLAN_MODE_TOKENS : 0);

  return {
    maxTokens: CONTEXT_WINDOW_BUDGET_TOKENS,
    percentage: Math.max(0, Math.min(100, Math.round((usedTokens / CONTEXT_WINDOW_BUDGET_TOKENS) * 100))),
    usedTokens,
  };
}

export function resolveBuilderContextUsage({
  backendContextState,
  composerSettings,
  draft,
  messages,
}: ResolveBuilderContextUsageParams): BuilderContextUsage {
  const hasAnyVisibleContext =
    draft.trim().length > 0 ||
    composerSettings.attachedFiles.length > 0 ||
    messages.length > 0;

  if (!backendContextState && !hasAnyVisibleContext) {
    return {
      maxTokens: CONTEXT_WINDOW_BUDGET_TOKENS,
      percentage: 0,
      usedTokens: 0,
    };
  }

  const localUsage = estimateBuilderContextUsage({
    composerSettings,
    draft,
    messages,
  });

  if (!backendContextState) {
    return localUsage;
  }

  const hasLiveLocalInputs =
    draft.trim().length > 0 ||
    composerSettings.attachedFiles.length > 0 ||
    messages.some((message) => message.isStreaming);

  if (hasLiveLocalInputs) {
    return localUsage;
  }

  return {
    maxTokens: backendContextState.maxTokens,
    percentage: backendContextState.percentage,
    usedTokens: backendContextState.usedTokens,
  };
}

function estimateTextTokens(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) {
    return 0;
  }

  const charCount = Array.from(trimmed).length;
  const wordCount = trimmed.split(/\s+/u).filter(Boolean).length;

  return Math.max(1, Math.round(charCount / 4), Math.round(wordCount * 1.35));
}
