import { useMemo } from "react";
import { builderPromptSuggestions } from "../mockBuilderAgent";
import { resolveBuilderContextUsage } from "../lib/context-window";
import { type PermissionMode, type ResponseSpeed } from "../lib/types";
import { useBuilderComposerSettings } from "./useBuilderComposerSettings";
import { useBuilderMessageSending } from "./useBuilderMessageSending";
import { useBuilderWorkspaceState } from "./useBuilderWorkspaceState";

export function useBuilderAgent() {
  const workspaceState = useBuilderWorkspaceState();
  const { composerSettings, persistComposerSettings } = useBuilderComposerSettings();
  const { isPreparingResponse, isStreaming, prepareProgress, sendMessage, stopStreaming } = useBuilderMessageSending({
    activeConversationId: workspaceState.activeConversationId,
    composerSettings,
    currentWorkspace: workspaceState.currentWorkspace,
    currentWorkspaceId: workspaceState.currentWorkspaceId,
    draft: workspaceState.draft,
    refreshWorkspaces: workspaceState.refreshWorkspaces,
    setActiveConversationId: workspaceState.setActiveConversationId,
    setContextStateMap: workspaceState.setContextStateMap,
    setCurrentWorkspaceId: workspaceState.setCurrentWorkspaceId,
    setDraft: workspaceState.setDraft,
    setMessageMap: workspaceState.setMessageMap,
  });

  const addAttachment = () => {
    void (async () => {
      const canBrowse = typeof window !== "undefined" && typeof window.electronAPI?.pickPath === "function";
      const picked = canBrowse ? await window.electronAPI?.pickPath?.("file") : window.prompt("File path")?.trim() ?? null;
      if (!picked) return;
      const normalizedPath = picked.trim();
      if (!normalizedPath) return;

      const nextFiles = composerSettings.attachedFiles.includes(normalizedPath)
        ? composerSettings.attachedFiles
        : [...composerSettings.attachedFiles, normalizedPath];
      persistComposerSettings({
        ...composerSettings,
        attachedFiles: nextFiles,
      });
    })();
  };

  const removeAttachment = (filePath: string) => {
    persistComposerSettings({
      ...composerSettings,
      attachedFiles: composerSettings.attachedFiles.filter((item) => item !== filePath),
    });
  };

  const setPermissionMode = (permissionMode: PermissionMode) => {
    persistComposerSettings({
      ...composerSettings,
      permissionMode,
    });
  };

  const setPlanMode = (planMode: boolean) => {
    persistComposerSettings({
      ...composerSettings,
      planMode,
    });
  };

  const setResponseSpeed = (responseSpeed: ResponseSpeed) => {
    persistComposerSettings({
      ...composerSettings,
      responseSpeed,
    });
  };

  const busyConversationIds = useMemo(
    () =>
      Object.entries(workspaceState.messageMap).flatMap(([conversationId, messages]) =>
        messages.some((message) => message.isStreaming) ? [conversationId] : [],
      ),
    [workspaceState.messageMap],
  );

  const contextUsage = useMemo(
    () =>
      resolveBuilderContextUsage({
        backendContextState: workspaceState.activeConversationId
          ? workspaceState.contextStateMap[workspaceState.activeConversationId] ?? null
          : null,
        composerSettings,
        draft: workspaceState.draft,
        messages: workspaceState.messages,
      }),
    [
      composerSettings,
      workspaceState.activeConversationId,
      workspaceState.contextStateMap,
      workspaceState.draft,
      workspaceState.messages,
    ],
  );

  return {
    activeConversation: workspaceState.activeConversation,
    activeConversationId: workspaceState.activeConversationId,
    currentWorkspace: workspaceState.currentWorkspace,
    draft: workspaceState.draft,
    isPreparingResponse,
    expandedWorkspaceIds: workspaceState.expandedWorkspaceIds,
    isStreaming,
    messages: workspaceState.messages,
    composerSettings,
    contextUsage,
    busyConversationIds,
    promptSuggestions: builderPromptSuggestions,
    prepareProgress,
    showAllWorkspaceIds: workspaceState.showAllWorkspaceIds,
    sortMode: workspaceState.sortMode,
    threadGroups: workspaceState.sortedThreadGroups,
    addAttachment,
    addWorkspace: workspaceState.addWorkspace,
    archiveWorkspaceThreads: workspaceState.archiveWorkspaceThreads,
    archiveThread: workspaceState.archiveThread,
    collapseAllWorkspaces: workspaceState.collapseAllWorkspaces,
    createPermanentWorktree: workspaceState.createPermanentWorktree,
    createWorkspaceThread: workspaceState.createWorkspaceThread,
    expandAllWorkspaces: workspaceState.expandAllWorkspaces,
    hasPreviousConversation: workspaceState.hasPreviousConversation,
    openConversation: workspaceState.openConversation,
    openWorkspaceInExplorer: workspaceState.openWorkspaceInExplorer,
    removeWorkspace: workspaceState.removeWorkspace,
    removeThread: workspaceState.removeThread,
    reorderWorkspaces: workspaceState.reorderWorkspaces,
    renameWorkspace: workspaceState.renameWorkspace,
    renameThread: workspaceState.renameThread,
    reopenPreviousConversation: workspaceState.reopenPreviousConversation,
    removeAttachment,
    sendMessage,
    stopStreaming,
    setPermissionMode,
    setPlanMode,
    setResponseSpeed,
    setDraft: workspaceState.setDraft,
    startNewChat: workspaceState.startNewChat,
    toggleSortMode: workspaceState.toggleSortMode,
    toggleWorkspace: workspaceState.toggleWorkspace,
    toggleWorkspaceShowAll: workspaceState.toggleWorkspaceShowAll,
  };
}
