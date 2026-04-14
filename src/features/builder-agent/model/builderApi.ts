import { fetchWithStartupRetry } from "@/shared/api/network";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export interface BuilderMessageDto {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  model: string | null;
}

export interface BuilderContextMemoryDto {
  id: string;
  memoryClass: string;
  title: string;
  content: string;
  updatedAt: string | null;
}

export interface BuilderContextStateDto {
  percentage: number;
  usedTokens: number;
  maxTokens: number;
  rollingSummary: string;
  recentMessageCount: number;
  memoryCount: number;
  memoryItems: BuilderContextMemoryDto[];
  updatedAt: string | null;
}

export interface BuilderThreadDto {
  id: string;
  workspaceId: string;
  title: string;
  updatedAt: string;
  messages: BuilderMessageDto[];
  contextState: BuilderContextStateDto | null;
}

export interface BuilderThreadSummaryDto {
  id: string;
  title: string;
  updatedAt: string;
}

export interface BuilderWorkspaceDto {
  id: string;
  label: string;
  path: string;
  updatedAt: string;
  threads: BuilderThreadSummaryDto[];
}

export interface SendBuilderMessagePayload {
  workspaceId: string;
  threadId: string | null;
  message: string;
  permissionMode: "default" | "full-access";
  planMode: boolean;
  responseSpeed: "normal" | "speed";
}

export interface SendBuilderMessageResult {
  thread: BuilderThreadDto;
  assistantMessage: BuilderMessageDto;
}

export interface SendBuilderMessageStreamHandlers {
  onToken: (token: string) => void;
  onAck?: (payload: { threadId: string; workspaceId: string; contextState: BuilderContextStateDto | null }) => void;
  onContextState?: (state: BuilderContextStateDto) => void;
  onReasoning?: (text: string) => void;
}

export async function listBuilderWorkspaces(): Promise<BuilderWorkspaceDto[]> {
  const data = await request<BuilderWorkspacesApiResponse>("/builder/workspaces");
  return data.items.map(mapWorkspace);
}

export async function createBuilderWorkspace(path: string, label?: string): Promise<BuilderWorkspaceDto> {
  const data = await request<BuilderWorkspaceApiResponse>("/builder/workspaces", {
    method: "POST",
    body: JSON.stringify({
      path,
      ...(label ? { label } : {}),
    }),
  });
  return mapWorkspace(data);
}

export async function renameBuilderWorkspace(workspaceId: string, label: string): Promise<BuilderWorkspaceDto> {
  const data = await request<BuilderWorkspaceApiResponse>(`/builder/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: JSON.stringify({ label }),
  });
  return mapWorkspace(data);
}

export async function deleteBuilderWorkspace(workspaceId: string): Promise<void> {
  await request<void>(`/builder/workspaces/${workspaceId}`, {
    method: "DELETE",
  });
}

export async function createBuilderThread(workspaceId: string, title?: string): Promise<BuilderThreadDto> {
  const data = await request<BuilderThreadApiResponse>(`/builder/workspaces/${workspaceId}/threads`, {
    method: "POST",
    body: JSON.stringify({
      ...(title ? { title } : {}),
    }),
  });
  return mapThread(data);
}

export async function archiveBuilderWorkspaceThreads(workspaceId: string): Promise<void> {
  await request<void>(`/builder/workspaces/${workspaceId}/threads/archive`, {
    method: "POST",
  });
}

export async function getBuilderThread(threadId: string): Promise<BuilderThreadDto> {
  const data = await request<BuilderThreadApiResponse>(`/builder/threads/${threadId}`);
  return mapThread(data);
}

export async function renameBuilderThread(threadId: string, title: string): Promise<BuilderThreadDto> {
  const data = await request<BuilderThreadApiResponse>(`/builder/threads/${threadId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return mapThread(data);
}

export async function deleteBuilderThread(threadId: string): Promise<void> {
  await request<void>(`/builder/threads/${threadId}`, {
    method: "DELETE",
  });
}

export async function archiveBuilderThread(threadId: string): Promise<void> {
  await request<void>(`/builder/threads/${threadId}/archive`, {
    method: "POST",
  });
}

export async function sendBuilderMessage(
  payload: SendBuilderMessagePayload,
  signal?: AbortSignal,
): Promise<SendBuilderMessageResult> {
  const data = await request<SendBuilderMessageApiResponse>("/builder/chat/messages", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      thread_id: payload.threadId,
      message: payload.message,
      permission_mode: payload.permissionMode,
      plan_mode: payload.planMode,
      response_speed: payload.responseSpeed,
    }),
    signal,
  });
  return {
    thread: mapThread(data.thread),
    assistantMessage: mapMessage(data.assistant_message),
  };
}

export async function sendBuilderMessageStream(
  payload: SendBuilderMessagePayload,
  handlers: SendBuilderMessageStreamHandlers,
  signal?: AbortSignal,
): Promise<SendBuilderMessageResult> {
  const response = await fetch(`${API_BASE_URL}/builder/chat/messages/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      thread_id: payload.threadId,
      message: payload.message,
      permission_mode: payload.permissionMode,
      plan_mode: payload.planMode,
      response_speed: payload.responseSpeed,
    }),
    signal,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // Ignore parse failures.
    }
    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error("Stream response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let finalResult: SendBuilderMessageResult | null = null;

  const processEventChunk = (chunk: string) => {
    const normalized = chunk.replace(/\r\n/g, "\n").trim();
    if (!normalized) return;
    const lines = normalized.split("\n");
    let eventName = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length === 0) return;
    const payloadText = dataLines.join("\n");
    const eventPayload = JSON.parse(payloadText) as Record<string, unknown>;

    if (eventName === "token") {
      const token = typeof eventPayload.text === "string" ? eventPayload.text : "";
      if (token) {
        handlers.onToken(token);
      }
      return;
    }
    if (eventName === "ack") {
      const contextState = mapContextState(eventPayload.context_state as BuilderContextStateApiResponse | null | undefined);
      const threadId = typeof eventPayload.thread_id === "string" ? eventPayload.thread_id : "";
      const workspaceId = typeof eventPayload.workspace_id === "string" ? eventPayload.workspace_id : "";
      if (threadId && workspaceId) {
        handlers.onAck?.({
          threadId,
          workspaceId,
          contextState,
        });
      }
      if (contextState) {
        handlers.onContextState?.(contextState);
      }
      return;
    }
    if (eventName === "reasoning") {
      const reasoning = typeof eventPayload.text === "string" ? eventPayload.text : "";
      if (reasoning) {
        handlers.onReasoning?.(reasoning);
      }
      return;
    }
    if (eventName === "done") {
      const thread = mapThread(eventPayload.thread as BuilderThreadApiResponse);
      if (thread.contextState) {
        handlers.onContextState?.(thread.contextState);
      }
      const assistantMessage = mapMessage(eventPayload.assistant_message as BuilderMessageApiResponse);
      finalResult = {
        thread,
        assistantMessage,
      };
      return;
    }
    if (eventName === "error") {
      const message = typeof eventPayload.message === "string" ? eventPayload.message : "Builder stream failed.";
      throw new Error(message);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      processEventChunk(chunk);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) {
    processEventChunk(buffer);
  }

  if (!finalResult) {
    throw new Error("Builder stream completed without final payload.");
  }
  return finalResult;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchWithStartupRetry(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // Ignore parse errors.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function mapWorkspace(data: BuilderWorkspaceApiResponse): BuilderWorkspaceDto {
  return {
    id: data.id,
    label: data.label,
    path: data.path,
    updatedAt: data.updated_at,
    threads: data.threads.map(mapThreadSummary),
  };
}

function mapThreadSummary(data: BuilderThreadSummaryApiResponse): BuilderThreadSummaryDto {
  return {
    id: data.id,
    title: data.title,
    updatedAt: data.updated_at,
  };
}

function mapMessage(data: BuilderMessageApiResponse): BuilderMessageDto {
  return {
    id: data.id,
    role: data.role,
    text: data.text,
    createdAt: data.created_at,
    model: data.model,
  };
}

function mapContextMemory(data: BuilderContextMemoryApiResponse): BuilderContextMemoryDto {
  return {
    id: data.id,
    memoryClass: data.memory_class,
    title: data.title,
    content: data.content,
    updatedAt: data.updated_at ?? null,
  };
}

function mapContextState(data: BuilderContextStateApiResponse | null | undefined): BuilderContextStateDto | null {
  if (!data) {
    return null;
  }
  return {
    percentage: data.percentage,
    usedTokens: data.used_tokens,
    maxTokens: data.max_tokens,
    rollingSummary: data.rolling_summary,
    recentMessageCount: data.recent_message_count,
    memoryCount: data.memory_count,
    memoryItems: data.memory_items.map(mapContextMemory),
    updatedAt: data.updated_at ?? null,
  };
}

function mapThread(data: BuilderThreadApiResponse): BuilderThreadDto {
  return {
    id: data.id,
    workspaceId: data.workspace_id,
    title: data.title,
    updatedAt: data.updated_at,
    messages: data.messages.map(mapMessage),
    contextState: mapContextState(data.context_state),
  };
}

interface BuilderMessageApiResponse {
  id: string;
  role: "user" | "assistant";
  text: string;
  created_at: string;
  model: string | null;
}

interface BuilderThreadSummaryApiResponse {
  id: string;
  title: string;
  updated_at: string;
}

interface BuilderContextMemoryApiResponse {
  id: string;
  memory_class: string;
  title: string;
  content: string;
  updated_at: string | null;
}

interface BuilderContextStateApiResponse {
  percentage: number;
  used_tokens: number;
  max_tokens: number;
  rolling_summary: string;
  recent_message_count: number;
  memory_count: number;
  memory_items: BuilderContextMemoryApiResponse[];
  updated_at: string | null;
}

interface BuilderWorkspaceApiResponse {
  id: string;
  label: string;
  path: string;
  updated_at: string;
  threads: BuilderThreadSummaryApiResponse[];
}

interface BuilderWorkspacesApiResponse {
  items: BuilderWorkspaceApiResponse[];
}

interface BuilderThreadApiResponse {
  id: string;
  workspace_id: string;
  title: string;
  updated_at: string;
  messages: BuilderMessageApiResponse[];
  context_state: BuilderContextStateApiResponse | null;
}

interface SendBuilderMessageApiResponse {
  thread: BuilderThreadApiResponse;
  assistant_message: BuilderMessageApiResponse;
}
