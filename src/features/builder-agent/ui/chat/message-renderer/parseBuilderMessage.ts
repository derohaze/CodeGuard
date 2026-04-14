import type { BuilderDescriptionListEntry, BuilderMessageBlock } from "./types";

const CODE_FENCE_REGEX = /^```([\w-]+)?\s*$/;
const HEADING_REGEX = /^(#{1,6})\s+(.+)$/;
const ORDERED_LIST_REGEX = /^\s*\d+\.\s+(.+)$/;
const UNORDERED_LIST_REGEX = /^\s*[-*+]\s+(.+)$/;
const SEPARATOR_REGEX = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const DESCRIPTION_ENTRY_REGEX = /^\s*([^:\n]{1,80}):\s+(.+)\s*$/;
const TABLE_SEPARATOR_REGEX = /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$/;

export function parseBuilderMessage(text: string): BuilderMessageBlock[] {
  const normalizedText = normalizeBuilderMessageText(text);
  const lines = normalizedText.replace(/\r\n/g, "\n").split("\n");
  const blocks: BuilderMessageBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index] ?? "";
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const fenceMatch = line.match(CODE_FENCE_REGEX);
    if (fenceMatch) {
      const language = fenceMatch[1]?.trim() || null;
      index += 1;
      const codeLines: string[] = [];
      while (index < lines.length && !CODE_FENCE_REGEX.test(lines[index] ?? "")) {
        codeLines.push(lines[index] ?? "");
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      const codeText = codeLines.join("\n");
      const fencedStructuredBlocks = language ? [] : parseStructuredFenceContent(codeText);
      if (fencedStructuredBlocks.length > 0) {
        blocks.push(...fencedStructuredBlocks);
      } else {
        blocks.push({ type: "code", code: codeText, language });
      }
      continue;
    }

    const headingMatch = trimmed.match(HEADING_REGEX);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: Math.min(headingMatch[1].length, 6) as 1 | 2 | 3 | 4 | 5 | 6,
        text: headingMatch[2].trim(),
      });
      index += 1;
      continue;
    }

    if (SEPARATOR_REGEX.test(trimmed)) {
      blocks.push({ type: "separator" });
      index += 1;
      continue;
    }

    if (isTableStart(lines, index)) {
      const tableLines: string[] = [lines[index] ?? ""];
      index += 2;
      while (index < lines.length) {
        const candidate = lines[index] ?? "";
        if (!candidate.trim() || !candidate.includes("|")) {
          break;
        }
        tableLines.push(candidate);
        index += 1;
      }

      const headers = splitTableRow(tableLines[0] ?? "");
      const rows = tableLines.slice(1).map(splitTableRow).filter((row) => row.length > 0);
      if (headers.length > 0 && rows.length > 0) {
        blocks.push({ type: "table", headers, rows });
        continue;
      }
    }

    const descriptionEntries = collectDescriptionEntries(lines, index);
    if (descriptionEntries.length >= 2) {
      blocks.push({ type: "description-list", entries: descriptionEntries });
      index += descriptionEntries.length;
      continue;
    }

    const listBlock = collectList(lines, index);
    if (listBlock) {
      blocks.push(listBlock.block);
      index = listBlock.nextIndex;
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length) {
      const current = lines[index] ?? "";
      const currentTrimmed = current.trim();
      if (!currentTrimmed) {
        break;
      }
      if (
        CODE_FENCE_REGEX.test(current) ||
        HEADING_REGEX.test(currentTrimmed) ||
        SEPARATOR_REGEX.test(currentTrimmed) ||
        isTableStart(lines, index) ||
        collectDescriptionEntries(lines, index).length >= 2 ||
        ORDERED_LIST_REGEX.test(currentTrimmed) ||
        UNORDERED_LIST_REGEX.test(currentTrimmed)
      ) {
        break;
      }
      paragraphLines.push(currentTrimmed);
      index += 1;
    }

    if (paragraphLines.length > 0) {
      blocks.push({
        type: "paragraph",
        text: paragraphLines.join(" "),
      });
      continue;
    }

    index += 1;
  }

  return blocks;
}

function normalizeBuilderMessageText(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t");
}

function collectDescriptionEntries(lines: string[], startIndex: number): BuilderDescriptionListEntry[] {
  const entries: BuilderDescriptionListEntry[] = [];
  let index = startIndex;

  while (index < lines.length) {
    const line = (lines[index] ?? "").trim();
    if (!line) {
      break;
    }
    const match = line.match(DESCRIPTION_ENTRY_REGEX);
    if (!match || line.includes("://")) {
      break;
    }
    entries.push({
      term: match[1].trim(),
      details: match[2].trim(),
    });
    index += 1;
  }

  return entries;
}

function collectList(lines: string[], startIndex: number) {
  const firstLine = (lines[startIndex] ?? "").trim();
  const ordered = ORDERED_LIST_REGEX.test(firstLine);
  const unordered = UNORDERED_LIST_REGEX.test(firstLine);
  if (!ordered && !unordered) {
    return null;
  }

  const items: string[] = [];
  let index = startIndex;

  while (index < lines.length) {
    const line = (lines[index] ?? "").trim();
    if (!line) {
      break;
    }
    const match = ordered ? line.match(ORDERED_LIST_REGEX) : line.match(UNORDERED_LIST_REGEX);
    if (!match) {
      break;
    }
    items.push(match[1].trim());
    index += 1;
  }

  return {
    block: {
      type: "list" as const,
      items,
      ordered,
    },
    nextIndex: index,
  };
}

function isTableStart(lines: string[], index: number): boolean {
  const headerLine = (lines[index] ?? "").trim();
  const separatorLine = (lines[index + 1] ?? "").trim();
  return headerLine.includes("|") && TABLE_SEPARATOR_REGEX.test(separatorLine);
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim())
    .filter((cell) => cell.length > 0);
}

function parseStructuredFenceContent(codeText: string): BuilderMessageBlock[] {
  const trimmed = codeText.trim();
  if (!trimmed) {
    return [];
  }

  const structuredSignalRegex =
    /(^#{1,6}\s)|(^\s*\d+\.\s+)|(^\s*[-*+]\s+)|(^\|.+\|$)|(^\s*[^:\n]{1,80}:\s+.+$)/m;
  if (!structuredSignalRegex.test(trimmed)) {
    return [];
  }

  const nestedBlocks = parseBuilderMessage(trimmed).filter((block) => block.type !== "code");
  if (nestedBlocks.length === 0) {
    return [];
  }

  const hasStructuredBlock = nestedBlocks.some((block) => block.type !== "paragraph");
  return hasStructuredBlock ? nestedBlocks : [];
}
