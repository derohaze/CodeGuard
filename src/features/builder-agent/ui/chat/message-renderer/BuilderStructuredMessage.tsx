import { useMemo, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { DescriptionDetails, DescriptionList, DescriptionTerm } from "@/components/ui/description-list";
import { Heading } from "@/components/ui/heading";
import { Separator } from "@/components/ui/separator";
import { ShowMore } from "@/components/ui/show-more";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Typography } from "@/components/ui/typography";
import { cn } from "@/lib/utils";
import { parseBuilderMessage } from "./parseBuilderMessage";
import type { BuilderMessageBlock } from "./types";

interface BuilderStructuredMessageProps {
  isStreaming: boolean;
  text: string;
  tone?: "default" | "inverted";
}

export function BuilderStructuredMessage({
  isStreaming,
  text,
  tone = "default",
}: BuilderStructuredMessageProps) {
  const blocks = useMemo(() => parseBuilderMessage(text), [text]);
  const isInverted = tone === "inverted";

  return (
    <Typography
      dir="auto"
      className={cn(
        "space-y-3.5 text-[14px] leading-7 text-start",
        isInverted &&
          "text-white [&_a]:text-[#f5d2a5] [&_code]:bg-white/10 [&_code]:text-white [&_blockquote]:border-white/20",
      )}
      style={{ unicodeBidi: "plaintext" }}
    >
      {blocks.map((block, index) => (
        <RenderedBlock
          key={`${block.type}-${index}`}
          block={block}
          isLast={index === blocks.length - 1}
          isStreaming={isStreaming}
          tone={tone}
        />
      ))}
    </Typography>
  );
}

function RenderedBlock({
  block,
  isLast,
  isStreaming,
  tone,
}: {
  block: BuilderMessageBlock;
  isLast: boolean;
  isStreaming: boolean;
  tone: "default" | "inverted";
}) {
  const isInverted = tone === "inverted";

  switch (block.type) {
    case "heading":
      return (
        <Heading level={block.level} className={cn("mt-6 first:mt-0", isInverted && "text-white")}>
          {renderInline(block.text)}
        </Heading>
      );
    case "paragraph":
      return (
        <p className={cn("leading-7 text-txt-primary", isInverted && "text-white")}>
          {renderInline(block.text)}
          {isStreaming && isLast ? (
            <span className="ml-0.5 inline-block h-5 w-[2px] animate-pulse align-[-2px] bg-current opacity-45" />
          ) : null}
        </p>
      );
    case "list": {
      const ListComp = block.ordered ? "ol" : "ul";
      return (
        <ListComp
          className={cn(
            "space-y-2 ps-6 text-txt-primary marker:text-[#94652a]",
            block.ordered ? "list-decimal" : "list-disc",
            isInverted && "text-white marker:text-[#f5d2a5]",
          )}
        >
          {block.items.map((item) => (
            <li key={item} className="ps-1 leading-7">
              {renderInline(item)}
            </li>
          ))}
        </ListComp>
      );
    }
    case "separator":
      return <Separator className={cn("my-5 bg-[hsl(var(--border-soft))]", isInverted && "bg-white/15")} />;
    case "description-list":
      return (
        <DescriptionList
          className={cn(
            "rounded-[20px] border border-border-soft bg-card/60 px-4 py-2",
            isInverted && "border-white/10 bg-white/5",
          )}
        >
          {block.entries.map((entry) => (
            <FragmentEntry
              key={`${entry.term}:${entry.details}`}
              term={entry.term}
              details={entry.details}
              tone={tone}
            />
          ))}
        </DescriptionList>
      );
    case "table":
      return (
        <ExpandableSection
          collapse={block.rows.length > 6}
          collapsedClassName="max-h-[320px]"
          labels={{
            less: "Show fewer rows",
            more: "Show more rows",
          }}
        >
          <div
            className={cn(
              "overflow-hidden rounded-[20px] border border-border-soft bg-card/60",
              isInverted && "border-white/10 bg-white/5",
            )}
          >
            <Table className="min-w-[420px] text-[13px]">
              <TableHeader>
                <TableRow
                  className={cn(
                    "border-border-soft bg-[#f4ede4] hover:bg-[#f4ede4]",
                    isInverted && "border-white/10 bg-white/10 hover:bg-white/10",
                  )}
                >
                  {block.headers.map((header) => (
                    <TableHead
                      key={header}
                      className={cn(
                        "h-11 px-4 text-[12px] font-semibold uppercase tracking-[0.08em] text-[#7d7467]",
                        isInverted && "text-[#e8dccd]",
                      )}
                    >
                      {renderInline(header)}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {block.rows.map((row, rowIndex) => (
                  <TableRow
                    key={`${rowIndex}-${row.join("|")}`}
                    className={cn(
                      "border-border-soft bg-transparent hover:bg-[#faf6ef]",
                      isInverted && "border-white/10 hover:bg-white/5",
                    )}
                  >
                    {row.map((cell, cellIndex) => (
                      <TableCell
                        key={`${rowIndex}-${cellIndex}`}
                        className={cn(
                          "px-4 py-3 align-top leading-[1.6rem] text-txt-primary",
                          isInverted && "text-white",
                        )}
                      >
                        {renderInline(cell)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </ExpandableSection>
      );
    case "code":
      return (
        <ExpandableSection
          collapse={block.code.split("\n").length > 14 || block.code.length > 900}
          collapsedClassName="max-h-[320px]"
          labels={{
            less: "Hide code",
            more: "Show code",
          }}
        >
          <div className="overflow-hidden rounded-[20px] border border-border-soft bg-[#201c18] text-[#f6efe6] shadow-[0_10px_24px_rgba(18,14,10,0.14)] [&_pre]:m-0 [&_pre]:bg-transparent [&_pre]:text-[#f6efe6] [&_pre]:whitespace-pre-wrap [&_pre]:break-words [&_pre_code]:rounded-none [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-inherit">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-[12px] text-[#cbb8a5]">
              <span>{block.language ?? "code"}</span>
            </div>
            <pre className="overflow-x-auto p-4 text-[12px] leading-[1.35rem]">
              <code className="block bg-transparent p-0 text-inherit">{block.code}</code>
            </pre>
          </div>
        </ExpandableSection>
      );
    default:
      return null;
  }
}

function FragmentEntry({
  details,
  term,
  tone,
}: {
  details: string;
  term: string;
  tone: "default" | "inverted";
}) {
  const isInverted = tone === "inverted";
  return (
    <>
      <DescriptionTerm className={cn(isInverted && "border-white/10 text-[#e8dccd]")}>
        {renderInline(term)}
      </DescriptionTerm>
      <DescriptionDetails className={cn(isInverted && "border-white/10 text-white")}>
        {renderInline(details)}
      </DescriptionDetails>
    </>
  );
}

function ExpandableSection({
  children,
  collapse,
  collapsedClassName,
  labels,
}: {
  children: ReactNode;
  collapse: boolean;
  collapsedClassName: string;
  labels: { less: string; more: string };
}) {
  const [expanded, setExpanded] = useState(false);

  if (!collapse) {
    return <>{children}</>;
  }

  return (
    <div className="space-y-2">
      <div className={cn("relative overflow-hidden", !expanded && collapsedClassName)}>
        {children}
        {!expanded && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-surface via-surface/95 to-transparent" />
        )}
      </div>
      <ShowMore className="my-0" onClick={() => setExpanded((current) => !current)}>
        {() => (
          <>
            <span>{expanded ? labels.less : labels.more}</span>
            <ChevronDown
              className={cn("size-4 transition-transform duration-200", expanded && "rotate-180")}
            />
          </>
        )}
      </ShowMore>
    </div>
  );
}

function renderInline(text: string): React.ReactNode {
  const nodes: React.ReactNode[] = [];
  const pattern = /(`[^`]+`)|(\[([^\]]+)\]\(([^)]+)\))|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      nodes.push(
        <code key={`${match.index}-code`}>{match[1].slice(1, -1)}</code>,
      );
    } else if (match[2]) {
      nodes.push(
        <a
          key={`${match.index}-link`}
          href={match[4]}
          target="_blank"
          rel="noreferrer"
        >
          {match[3]}
        </a>,
      );
    } else if (match[5]) {
      nodes.push(
        <strong key={`${match.index}-strong`}>
          {renderInline(match[6])}
        </strong>,
      );
    } else if (match[7]) {
      nodes.push(
        <em key={`${match.index}-em`}>
          {renderInline(match[8])}
        </em>,
      );
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : text;
}
