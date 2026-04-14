import { useEffect, useRef, useState } from "react";

const THREAD_TITLE_TYPING_INTERVAL_MS = 18;

export function AnimatedThreadTitle({ title }: { title: string }) {
  const [visibleTitle, setVisibleTitle] = useState(title);
  const previousTitleRef = useRef(title);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    const previousTitle = previousTitleRef.current;
    if (previousTitle === title) {
      setVisibleTitle(title);
      return;
    }

    previousTitleRef.current = title;

    const glyphs = Array.from(title);
    if (glyphs.length === 0) {
      setVisibleTitle("");
      return;
    }

    let cursor = 0;
    setVisibleTitle("");

    const tick = () => {
      cursor = Math.min(cursor + resolveTitleTypingStep(glyphs.length, cursor), glyphs.length);
      setVisibleTitle(glyphs.slice(0, cursor).join(""));

      if (cursor < glyphs.length) {
        timeoutRef.current = window.setTimeout(tick, THREAD_TITLE_TYPING_INTERVAL_MS);
      } else {
        timeoutRef.current = null;
      }
    };

    timeoutRef.current = window.setTimeout(tick, 0);
  }, [title]);

  return (
    <span className="min-w-0 truncate text-[12px] font-medium text-txt-primary" dir="auto" style={{ unicodeBidi: "plaintext" }}>
      {visibleTitle}
    </span>
  );
}

function resolveTitleTypingStep(totalLength: number, cursor: number): number {
  const remaining = totalLength - cursor;
  if (remaining <= 2) {
    return remaining;
  }
  if (totalLength >= 24) {
    return 2;
  }
  return 1;
}
