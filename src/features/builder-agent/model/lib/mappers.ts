import type { BuilderThreadDto, BuilderWorkspaceDto } from "../builderApi";
import type { BuilderMessage, BuilderThreadGroup } from "../mockBuilderAgent";

export function formatRelativeTime(isoValue: string): string {
  const parsed = parseBuilderTimestamp(isoValue);
  if (Number.isNaN(parsed.getTime())) {
    return "--:--";
  }

  const now = new Date();
  const isSameDay =
    parsed.getFullYear() === now.getFullYear()
    && parsed.getMonth() === now.getMonth()
    && parsed.getDate() === now.getDate();

  if (isSameDay) {
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(parsed);
  }

  const isSameYear = parsed.getFullYear() === now.getFullYear();
  return new Intl.DateTimeFormat(
    "en-US",
    isSameYear
      ? {
          month: "short",
          day: "numeric",
        }
      : {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        },
  ).format(parsed);
}

function parseBuilderTimestamp(value: string): Date {
  const trimmed = value.trim();
  if (!trimmed) {
    return new Date(Number.NaN);
  }

  const hasExplicitTimezone = /(?:Z|[+-]\d{2}:\d{2})$/u.test(trimmed);
  return new Date(hasExplicitTimezone ? trimmed : `${trimmed}Z`);
}

export function mapMessage(message: BuilderThreadDto["messages"][number]): BuilderMessage {
  return {
    id: message.id,
    role: message.role,
    text: message.text,
    isStreaming: false,
  };
}

export function mapWorkspace(workspace: BuilderWorkspaceDto): BuilderThreadGroup {
  return {
    id: workspace.id,
    label: workspace.label,
    path: workspace.path,
    threads: workspace.threads.map((thread) => ({
      id: thread.id,
      title: thread.title,
      rawUpdatedAt: thread.updatedAt,
      updatedAt: formatRelativeTime(thread.updatedAt),
    })),
  };
}
