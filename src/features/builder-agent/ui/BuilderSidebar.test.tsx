import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BuilderSidebar } from "./BuilderSidebar";

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  Reorder: {
    Group: ({ children }: { children?: ReactNode } & Record<string, unknown>) => <div>{children}</div>,
    Item: ({ children }: { children?: ReactNode } & Record<string, unknown>) => <div>{children}</div>,
  },
  motion: {
    aside: ({ children, initial: _initial, animate: _animate, transition: _transition, ...props }: { children?: ReactNode } & Record<string, unknown>) => (
      <aside {...props}>{children}</aside>
    ),
    div: ({ children, initial: _initial, animate: _animate, exit: _exit, transition: _transition, layout: _layout, whileDrag: _whileDrag, ...props }: { children?: ReactNode } & Record<string, unknown>) => (
      <div {...props}>{children}</div>
    ),
    button: ({ children, initial: _initial, animate: _animate, exit: _exit, transition: _transition, ...props }: { children?: ReactNode } & Record<string, unknown>) => (
      <button {...props}>{children}</button>
    ),
  },
}));

vi.mock("@/shared/ui/WorkspaceModeSwitch", () => ({
  WorkspaceModeSwitch: () => <div data-testid="workspace-mode-switch" />,
}));

vi.mock("./BuilderCommandMenu", () => ({
  BuilderCommandMenu: () => null,
}));

describe("BuilderSidebar", () => {
  it("types updated thread titles instead of replacing them all at once", () => {
    vi.useFakeTimers();

    const props = {
      activeConversationId: "thread-1",
      busyConversationIds: [],
      currentWorkspaceId: "workspace-1",
      expandedWorkspaceIds: ["workspace-1"],
      hasPreviousConversation: false,
      isCollapsed: false,
      onAddWorkspace: vi.fn(),
      onArchiveThread: vi.fn(),
      onArchiveWorkspaceThreads: vi.fn(),
      onCollapseAllWorkspaces: vi.fn(),
      onCreatePermanentWorktree: vi.fn(),
      onCreateWorkspaceThread: vi.fn(),
      onExpandAllWorkspaces: vi.fn(),
      onOpenConversation: vi.fn(),
      onOpenSettings: vi.fn(),
      onOpenWorkspaceInExplorer: vi.fn(),
      onRemoveWorkspace: vi.fn(),
      onRemoveThread: vi.fn(),
      onReorderWorkspaces: vi.fn(),
      onRenameWorkspace: vi.fn(),
      onRenameThread: vi.fn(),
      onReopenPreviousConversation: vi.fn(),
      onToggleCollapse: vi.fn(),
      onToggleWorkspace: vi.fn(),
      onToggleWorkspaceShowAll: vi.fn(),
      onWorkspaceModeChange: vi.fn(),
      showAllWorkspaceIds: [],
      workspaceMode: "builder" as const,
    };

    const { rerender } = render(
      <TooltipProvider>
        <BuilderSidebar
          {...props}
          threadGroups={[
            {
              id: "workspace-1",
              label: "project x",
              path: "D:\\workspace\\project-x",
              threads: [{ id: "thread-1", title: "New chat", updatedAt: "now" }],
            },
          ]}
        />
      </TooltipProvider>,
    );

    expect(screen.getByText("New chat")).toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <BuilderSidebar
          {...props}
          threadGroups={[
            {
              id: "workspace-1",
              label: "project x",
              path: "D:\\workspace\\project-x",
              threads: [{ id: "thread-1", title: "Mind Misery", updatedAt: "now" }],
            },
          ]}
        />
      </TooltipProvider>,
    );

    expect(screen.queryByText("Mind Misery")).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(0);
    });

    expect(screen.getByText("M")).toBeInTheDocument();
    expect(screen.queryByText("Mind Misery")).not.toBeInTheDocument();

    act(() => {
      vi.runAllTimers();
    });

    expect(screen.getByText("Mind Misery")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("shows a working indicator for busy threads", () => {
    render(
      <TooltipProvider>
        <BuilderSidebar
          activeConversationId="thread-1"
          busyConversationIds={["thread-1"]}
          currentWorkspaceId="workspace-1"
          expandedWorkspaceIds={["workspace-1"]}
          hasPreviousConversation={false}
          isCollapsed={false}
          onAddWorkspace={vi.fn()}
          onArchiveThread={vi.fn()}
          onArchiveWorkspaceThreads={vi.fn()}
          onCollapseAllWorkspaces={vi.fn()}
          onCreatePermanentWorktree={vi.fn()}
          onCreateWorkspaceThread={vi.fn()}
          onExpandAllWorkspaces={vi.fn()}
          onOpenConversation={vi.fn()}
          onOpenSettings={vi.fn()}
          onOpenWorkspaceInExplorer={vi.fn()}
          onRemoveWorkspace={vi.fn()}
          onRemoveThread={vi.fn()}
          onReorderWorkspaces={vi.fn()}
          onRenameWorkspace={vi.fn()}
          onRenameThread={vi.fn()}
          onReopenPreviousConversation={vi.fn()}
          onToggleCollapse={vi.fn()}
          onToggleWorkspace={vi.fn()}
          onToggleWorkspaceShowAll={vi.fn()}
          onWorkspaceModeChange={vi.fn()}
          showAllWorkspaceIds={[]}
          threadGroups={[
            {
              id: "workspace-1",
              label: "project x",
              path: "D:\\workspace\\project-x",
              threads: [{ id: "thread-1", title: "Mind Misery", updatedAt: "now" }],
            },
          ]}
          workspaceMode="builder"
        />
      </TooltipProvider>,
    );

    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByRole("presentation", { hidden: true })).toBeInTheDocument();
  });
});
