import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";

const ROOT = resolve(process.cwd(), "src");
const BUILDER_ROOT_SEGMENT = "/src/features/builder-agent/";
const CODE_FILE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx"]);

function walkFiles(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      files.push(...walkFiles(fullPath));
    } else {
      files.push(fullPath);
    }
  }
  return files;
}

function normalize(value: string): string {
  return value.replaceAll("\\", "/");
}

describe("builder boundary rules", () => {
  it("keeps builder-named files inside the builder feature", () => {
    const allFiles = walkFiles(ROOT);
    const leakingFiles = allFiles.filter((filePath) => {
      const path = normalize(filePath).toLowerCase();
      const isBuilderNamed = path.includes("builder") || path.includes("/builder-agent/");
      if (!isBuilderNamed) return false;
      return !path.includes(BUILDER_ROOT_SEGMENT);
    });
    expect(leakingFiles).toEqual([]);
  });

  it("uses builder barrel import outside the feature", () => {
    const allCodeFiles = walkFiles(ROOT).filter((filePath) => CODE_FILE_EXTENSIONS.has(extname(filePath)));
    const deepImportViolations: string[] = [];

    for (const filePath of allCodeFiles) {
      const path = normalize(filePath);
      if (path.includes(BUILDER_ROOT_SEGMENT)) {
        continue;
      }

      const content = readFileSync(filePath, "utf8");
      if (
        content.includes('from "@/features/builder-agent/') ||
        content.includes("from '@/features/builder-agent/")
      ) {
        deepImportViolations.push(normalize(relative(ROOT, filePath)));
      }
    }

    expect(deepImportViolations).toEqual([]);
  });
});

