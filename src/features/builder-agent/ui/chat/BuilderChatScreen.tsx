import { useCallback, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { BuilderComposer } from "./BuilderComposer";
import { BuilderConversationView } from "./BuilderConversationView";
import { BuilderNewChat } from "./BuilderNewChat";
import type { BuilderChatScreenProps } from "./types";

export function BuilderChatScreen({
  activeConversationId,
  composerSettings,
  contextUsage,
  currentWorkspaceId,
  currentWorkspacePath,
  conversationTitle,
  conversationSubtitle,
  draft,
  isNewChat,
  prepareProgress,
  isPreparingResponse,
  isStreaming,
  messages,
  promptSuggestions,
  onArchiveConversation,
  onOpenWorkspaceInExplorer,
  onPermissionModeChange,
  onPickAttachment,
  onPlanModeChange,
  onRenameConversation,
  onDraftChange,
  onRemoveAttachment,
  onSend,
  onStopStreaming,
  onCreatePermanentWorktree,
}: BuilderChatScreenProps) {
  const scrollToLatestRef = useRef<(() => void) | null>(null);
  const pendingScrollFrameRef = useRef<number | null>(null);

  const handleSendRequest = useCallback(() => {
    scrollToLatestRef.current?.();
    onSend();
    if (pendingScrollFrameRef.current !== null) {
      window.cancelAnimationFrame(pendingScrollFrameRef.current);
    }
    pendingScrollFrameRef.current = window.requestAnimationFrame(() => {
      pendingScrollFrameRef.current = window.requestAnimationFrame(() => {
        scrollToLatestRef.current?.();
        pendingScrollFrameRef.current = null;
      });
    });
  }, [onSend]);

  const handleSuggestionSelect = useCallback((prompt: string) => {
    scrollToLatestRef.current?.();
    onSend(prompt);
    if (pendingScrollFrameRef.current !== null) {
      window.cancelAnimationFrame(pendingScrollFrameRef.current);
    }
    pendingScrollFrameRef.current = window.requestAnimationFrame(() => {
      pendingScrollFrameRef.current = window.requestAnimationFrame(() => {
        scrollToLatestRef.current?.();
        pendingScrollFrameRef.current = null;
      });
    });
  }, [onSend]);

  useEffect(() => () => {
    if (pendingScrollFrameRef.current !== null) {
      window.cancelAnimationFrame(pendingScrollFrameRef.current);
      pendingScrollFrameRef.current = null;
    }
  }, []);

  return (
    <motion.div
      initial={false}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.14 }}
      className="flex min-h-0 flex-1 flex-col bg-surface"
    >
      {isNewChat ? (
        <BuilderNewChat
          promptSuggestions={promptSuggestions}
          workspaceLabel={conversationSubtitle}
          onSelectSuggestion={handleSuggestionSelect}
        />
      ) : (
        <BuilderConversationView
          activeConversationId={activeConversationId}
          currentWorkspaceId={currentWorkspaceId}
          currentWorkspacePath={currentWorkspacePath}
          conversationSubtitle={conversationSubtitle}
          conversationTitle={conversationTitle}
          messages={messages}
          onArchiveConversation={onArchiveConversation}
          onCreatePermanentWorktree={onCreatePermanentWorktree}
          onOpenWorkspaceInExplorer={onOpenWorkspaceInExplorer}
          onRenameConversation={onRenameConversation}
          registerScrollToLatest={(callback) => {
            scrollToLatestRef.current = callback;
          }}
        />
      )}

      <BuilderComposer
        composerSettings={composerSettings}
        contextUsage={contextUsage}
        draft={draft}
        prepareProgress={prepareProgress}
        isPreparingResponse={isPreparingResponse}
        isStreaming={isStreaming}
        onDraftChange={onDraftChange}
        onPermissionModeChange={onPermissionModeChange}
        onPickAttachment={onPickAttachment}
        onPlanModeChange={onPlanModeChange}
        onRemoveAttachment={onRemoveAttachment}
        onSend={handleSendRequest}
        onStopStreaming={onStopStreaming}
      />
    </motion.div>
  );
}
