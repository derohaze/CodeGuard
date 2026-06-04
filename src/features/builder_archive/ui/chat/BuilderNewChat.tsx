import type { BuilderPromptSuggestion } from "../../model/mockBuilderAgent";

export function BuilderNewChat({
  promptSuggestions,
  workspaceLabel,
  onSelectSuggestion,
}: {
  promptSuggestions: BuilderPromptSuggestion[];
  workspaceLabel: string;
  onSelectSuggestion: (prompt: string) => void;
}) {
  return (
    <div className="flex flex-1 items-center justify-center dotted-bg px-8 py-10">
      <div className="mx-auto flex w-full max-w-[980px] flex-col items-center">
        <h2 className="text-[42px] font-semibold tracking-[-0.05em] text-txt-primary">Let&apos;s build</h2>
        <p className="mt-2 text-[18px] text-txt-secondary">{workspaceLabel}</p>

        <div className="mt-12 grid w-full grid-cols-3 gap-4 max-[1100px]:grid-cols-1">
          {promptSuggestions.map((suggestion) => (
            <button
              key={suggestion.id}
              type="button"
              onClick={() => onSelectSuggestion(suggestion.title)}
              className="rounded-[24px] border bg-[#f4f4f5] px-5 py-5 text-left shadow-[0_10px_24px_rgba(0,0,0,0.05)] transition-colors hover:bg-[#e5e5e5]"
              style={{ borderColor: "hsl(var(--border-soft))" }}
            >
              <p className="text-[18px] font-medium leading-7 text-txt-primary">{suggestion.title}</p>
              <p className="mt-2 text-sm leading-6 text-txt-secondary">{suggestion.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
