import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BuilderMessageText } from "./BuilderMessageText";

describe("BuilderMessageText", () => {
  it("renders headings, lists, tables, and description lists with structured markup", () => {
    render(
      <BuilderMessageText
        isStreaming={false}
        text={[
          "## System Design",
          "",
          "1. **Input** enters the system",
          "2. **Output** leaves the system",
          "",
          "| Layer | Role |",
          "| --- | --- |",
          "| UI | React client |",
          "| API | FastAPI service |",
          "",
          "Owner: Platform team",
          "Status: Active",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("heading", { name: "System Design" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("React client")).toBeInTheDocument();
    expect(screen.getByText("Platform team")).toBeInTheDocument();
    expect(
      screen.getByText((_, element) => element?.textContent === "Input enters the system"),
    ).toBeInTheDocument();
  });

  it("collapses long code blocks behind a show more action", () => {
    const code = Array.from({ length: 18 }, (_, index) => `line_${index + 1} = ${index + 1}`).join("\n");

    render(
      <BuilderMessageText
        isStreaming={false}
        text={`\`\`\`python\n${code}\n\`\`\``}
      />,
    );

    expect(screen.getByText("Show code")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    const codeElement = document.querySelector("pre code");
    expect(codeElement).not.toBeNull();
    expect(codeElement?.className).toContain("bg-transparent");
  });

  it("renders fenced markdown tables as structured content when no code language is provided", () => {
    render(
      <BuilderMessageText
        isStreaming={false}
        text={[
          "```",
          "| Organization | Focus |",
          "| --- | --- |",
          "| ISO | General standards |",
          "| OECD | Economic cooperation |",
          "```",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.queryByText("code")).not.toBeInTheDocument();
    expect(screen.getByText("General standards")).toBeInTheDocument();
  });

  it("supports inverted tone for user bubbles", () => {
    render(
      <BuilderMessageText
        isStreaming={false}
        text="Client message"
        tone="inverted"
      />,
    );

    const text = screen.getByText("Client message");
    expect(text).toBeInTheDocument();
    expect(text.className).toContain("text-white");
  });

  it("normalizes escaped newlines before structured rendering", () => {
    render(
      <BuilderMessageText
        isStreaming={false}
        text={"## Title\\n\\nSecond paragraph"}
      />,
    );

    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("Second paragraph")).toBeInTheDocument();
  });
});
