import * as React from "react";
import { cn } from "@/lib/utils";

interface ProgressCircleProps extends React.ComponentPropsWithoutRef<"div"> {
  value?: number;
  isIndeterminate?: boolean;
  size?: number;
  strokeWidth?: number;
  trackColor?: string;
  indicatorColor?: string;
}

export function ProgressCircle({
  className,
  value = 0,
  isIndeterminate = false,
  size = 18,
  strokeWidth = 3,
  trackColor = "rgba(111, 97, 74, 0.22)",
  indicatorColor = "#3f8f63",
  ...props
}: ProgressCircleProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const visiblePercentage = clamped === 0 ? 0 : Math.max(clamped, 6);
  const c = size / 2;
  const r = c - 2;
  const dashOffset = 100 - visiblePercentage;

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={isIndeterminate ? undefined : clamped}
      className={cn("inline-flex shrink-0 items-center justify-center", className)}
      {...props}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        fill="none"
        aria-hidden="true"
        className="shrink-0"
      >
        <circle
          data-slot="progress-circle-track"
          cx={c}
          cy={c}
          r={r}
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />
        <circle
          data-slot="progress-circle-indicator"
          cx={c}
          cy={c}
          r={r}
          stroke={indicatorColor}
          strokeWidth={strokeWidth}
          pathLength={100}
          strokeDasharray="100 200"
          strokeDashoffset={isIndeterminate ? 70 : dashOffset}
          strokeLinecap="round"
          transform={`rotate(-90 ${c} ${c})`}
          className={cn(
            "origin-center transition-[stroke-dashoffset] duration-150 ease-out",
            isIndeterminate && "animate-[spin_1s_cubic-bezier(0.4,0,0.2,1)_infinite]",
          )}
        />
      </svg>
    </div>
  );
}
