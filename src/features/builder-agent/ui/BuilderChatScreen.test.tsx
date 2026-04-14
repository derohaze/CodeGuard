import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BuilderChatScreen } from "./BuilderChatScreen";

vi.mock("@/components/ui/shiny-text", () => ({
  ShinyText: ({ text, className }: { text: string; className?: string }) => <span className={className}>{text}</span>,
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, initial: _initial, animate: _animate, exit: _exit, transition: _transition, ...props }: { children?: ReactNode } & Record<string, unknown>) => (
      <div {...props}>{children}</div>
    ),
    button: ({ children, initial: _initial, animate: _animate, exit: _exit, transition: _transition, ...props }: { children?: ReactNode } & Record<string, unknown>) => (
      <button {...props}>{children}</button>
    ),
  },
}));

describe("BuilderChatScreen", () => {
  it("hides placeholder model controls and shows a thinking state while streaming", () => {
    render(
      <TooltipProvider>
        <BuilderChatScreen
          activeConversationId="thread-1"
          composerSettings={{
            permissionMode: "full-access",
            planMode: false,
            responseSpeed: "normal",
            attachedFiles: [],
          }}
          currentWorkspaceId={null}
          currentWorkspacePath={null}
          conversationTitle="New chat"
          conversationSubtitle="workspace"
          draft=""
          isNewChat={false}
          isStreaming
          messages={[
            {
              id: "assistant-1",
              role: "assistant",
              text: "",
              isStreaming: true,
              reasoningLines: [],
            },
          ]}
          promptSuggestions={[]}
          onArchiveConversation={vi.fn()}
          onOpenWorkspaceInExplorer={vi.fn()}
          onPermissionModeChange={vi.fn()}
          onPickAttachment={vi.fn()}
          onPlanModeChange={vi.fn()}
          onRenameConversation={vi.fn()}
          onDraftChange={vi.fn()}
          onRemoveAttachment={vi.fn()}
          onSend={vi.fn()}
          onStopStreaming={vi.fn()}
          onCreatePermanentWorktree={vi.fn()}
        />
      </TooltipProvider>,
    );

    expect(screen.queryByText("GPT-5.4")).not.toBeInTheDocument();
    expect(screen.queryByText("Medium")).not.toBeInTheDocument();
    expect(screen.getByText("Thinking")).toBeInTheDocument();
    expect(screen.queryByLabelText("Jump to latest message")).not.toBeInTheDocument();
  });
});
