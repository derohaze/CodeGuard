import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const CURRENT_DIR = path.dirname(fileURLToPath(import.meta.url));
export const BACKEND_ROOT = path.resolve(CURRENT_DIR, "../..");
export const PROJECT_ROOT = path.resolve(BACKEND_ROOT, "..");

loadBackendEnv(path.join(BACKEND_ROOT, ".env"));

export interface GatewayConfig {
  host: string;
  port: number;
  pythonApiBaseUrl: string;
  corsAllowedOrigins: string[];
  maxBodyBytes: number;
  requestTimeoutMs: number;
  upstreamConnectTimeoutMs: number;
}

const DEFAULT_CORS_ORIGINS = "http://localhost:8080,http://127.0.0.1:8080,http://[::1]:8080,null";

export const config: GatewayConfig = {
  host: env("NODE_GATEWAY_HOST", "127.0.0.1"),
  port: intEnv("NODE_GATEWAY_PORT", 7000, 1, 65535),
  pythonApiBaseUrl: trimTrailingSlash(env("PYTHON_API_BASE_URL", `http://127.0.0.1:${env("APP_PORT", "8000")}`)),
  corsAllowedOrigins: listEnv(
    "NODE_GATEWAY_CORS_ORIGINS",
    mergeListValues(env("APP_CORS_ORIGINS", ""), DEFAULT_CORS_ORIGINS),
  ),
  maxBodyBytes: intEnv("NODE_GATEWAY_MAX_BODY_MB", 25, 1, 1024) * 1024 * 1024,
  requestTimeoutMs: intEnv("NODE_GATEWAY_REQUEST_TIMEOUT_SECONDS", 120, 5, 600) * 1000,
  upstreamConnectTimeoutMs: intEnv("NODE_GATEWAY_UPSTREAM_CONNECT_TIMEOUT_SECONDS", 10, 1, 120) * 1000,
};

function loadBackendEnv(envFile: string): void {
  try {
    const content = readFileSync(envFile, "utf8");
    for (const rawLine of content.split(/\r?\n/u)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const separator = line.indexOf("=");
      if (separator <= 0) continue;

      const key = line.slice(0, separator).trim();
      const value = stripQuotes(line.slice(separator + 1).trim());
      if (!(key in process.env)) {
        process.env[key] = value;
      }
    }
  } catch {
    // Python already owns backend/.env validation. The gateway only mirrors values it needs.
  }
}

function stripQuotes(value: string): string {
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  return value;
}

function env(key: string, fallback: string): string {
  const value = process.env[key]?.trim();
  return value && value.length > 0 ? value : fallback;
}

function intEnv(key: string, fallback: number, min: number, max: number): number {
  const raw = process.env[key]?.trim();
  const parsed = raw ? Number(raw) : fallback;
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${key} must be an integer between ${min} and ${max}.`);
  }
  return parsed;
}

function listEnv(key: string, fallback: string): string[] {
  const raw = env(key, fallback);
  return splitList(raw);
}

function mergeListValues(...values: string[]): string {
  return [...new Set(values.flatMap(splitList))].join(",");
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/u, "");
}
