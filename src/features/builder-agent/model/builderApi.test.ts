import { afterEach, describe, expect, it, vi } from "vitest";
import { sendBuilderMessageStream } from "./builderApi";

const encoder = new TextEncoder();

function buildStreamResponse(chunks: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

describe("sendBuilderMessageStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("captures context state from stream ack and final payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: buildStreamResponse([
        'event: ack\ndata: {"type":"ack","thread_id":"thread-1","workspace_id":"workspace-1","context_state":{"percentage":18,"used_tokens":4320,"max_tokens":24000,"rolling_summary":"Initial context.","recent_message_count":1,"memory_count":0,"memory_items":[],"updated_at":"2026-04-14T00:00:00Z"}}\n\n',
        'event: token\ndata: {"type":"token","text":"Hello"}\n\n',
        'event: done\ndata: {"type":"done","thread":{"id":"thread-1","workspace_id":"workspace-1","title":"New chat","updated_at":"2026-04-14T00:00:01Z","messages":[{"id":"user-1","role":"user","text":"Hi","created_at":"2026-04-14T00:00:00Z","model":null},{"id":"assistant-1","role":"assistant","text":"Hello","created_at":"2026-04-14T00:00:01Z","model":"route/glm-5.1"}],"context_state":{"percentage":22,"used_tokens":5280,"max_tokens":24000,"rolling_summary":"Updated context.","recent_message_count":2,"memory_count":1,"memory_items":[{"id":"memory-1","memory_class":"goal","title":"Greeting","content":"User greeted the builder.","updated_at":"2026-04-14T00:00:01Z"}],"updated_at":"2026-04-14T00:00:01Z"}},"assistant_message":{"id":"assistant-1","role":"assistant","text":"Hello","created_at":"2026-04-14T00:00:01Z","model":"route/glm-5.1"}}\n\n',
      ]),
    });
    vi.stubGlobal("fetch", fetchMock);

    const onToken = vi.fn();
    const onContextState = vi.fn();
    const onAck = vi.fn();

    const result = await sendBuilderMessageStream(
      {
        workspaceId: "workspace-1",
        threadId: "thread-1",
        message: "Hi",
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
      },
      {
        onAck,
        onToken,
        onContextState,
      },
    );

    expect(onAck).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "thread-1",
        workspaceId: "workspace-1",
      }),
    );
    expect(onToken).toHaveBeenCalledWith("Hello");
    expect(onContextState).toHaveBeenCalledWith(
      expect.objectContaining({
        percentage: 18,
        usedTokens: 4320,
      }),
    );
    expect(result.thread.contextState).toEqual(
      expect.objectContaining({
        percentage: 22,
        memoryCount: 1,
      }),
    );
    expect(result.thread.contextState?.memoryItems[0]).toEqual(
      expect.objectContaining({
        memoryClass: "goal",
        title: "Greeting",
      }),
    );
  });
});
