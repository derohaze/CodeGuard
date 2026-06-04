import http from "node:http";
import https from "node:https";
import type { IncomingHttpHeaders, IncomingMessage, RequestOptions, ServerResponse } from "node:http";
import { Transform, pipeline } from "node:stream";
import { config } from "./config.js";
import { logProxyError } from "./logger.js";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
]);

const UPSTREAM_CONTROLLED_CORS_HEADERS = new Set([
  "access-control-allow-origin",
  "access-control-allow-methods",
  "access-control-allow-headers",
  "access-control-allow-credentials",
]);

class BodyTooLargeError extends Error {
  constructor() {
    super("Request body exceeds the configured gateway limit.");
  }
}

export function proxyToPython(request: IncomingMessage, response: ServerResponse, requestUrl: URL): void {
  const declaredLength = parseContentLength(request.headers["content-length"]);
  if (declaredLength === "invalid") {
    request.resume();
    sendProxyJson(response, 400, { detail: "Invalid Content-Length header." });
    return;
  }
  if (declaredLength !== null && declaredLength > config.maxBodyBytes) {
    request.resume();
    sendProxyJson(response, 413, { detail: "Request body is too large." });
    return;
  }

  const targetUrl = new URL(`${requestUrl.pathname}${requestUrl.search}`, config.pythonApiBaseUrl);
  const transport = targetUrl.protocol === "https:" ? https : http;
  const headers = buildProxyHeaders(request.headers);
  const options: RequestOptions = {
    protocol: targetUrl.protocol,
    hostname: targetUrl.hostname,
    port: targetUrl.port,
    path: `${targetUrl.pathname}${targetUrl.search}`,
    method: request.method,
    headers,
  };

  let bodyRejected = false;
  const upstreamRequest = transport.request(options, (upstreamResponse) => {
    clearTimeout(upstreamConnectTimer);
    response.writeHead(upstreamResponse.statusCode ?? 502, filterResponseHeaders(upstreamResponse.headers));
    upstreamResponse.pipe(response);
  });

  const upstreamConnectTimer = setTimeout(() => {
    upstreamRequest.destroy(new Error("Python API connection timed out."));
  }, config.upstreamConnectTimeoutMs);

  upstreamRequest.on("error", () => {
    clearTimeout(upstreamConnectTimer);
    if (bodyRejected || response.writableEnded) return;
    logProxyError(request.method ?? "GET", requestUrl.pathname);
    sendProxyJson(response, 502, { detail: "Python security API is unavailable." });
  });

  pipeline(request, limitRequestBody(), upstreamRequest, (error) => {
    if (error instanceof BodyTooLargeError) {
      bodyRejected = true;
      upstreamRequest.destroy();
      sendProxyJson(response, 413, { detail: "Request body is too large." });
      return;
    }

    if (error) {
      upstreamRequest.destroy(error);
    }
  });
}

function buildProxyHeaders(headers: IncomingHttpHeaders): Record<string, string | string[]> {
  const result: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (value === undefined || HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
    result[key] = value;
  }
  result["x-forwarded-host"] = `${config.host}:${config.port}`;
  result["x-forwarded-proto"] = "http";
  return result;
}

function filterResponseHeaders(headers: IncomingHttpHeaders): Record<string, string | string[]> {
  const result: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(headers)) {
    const lowerKey = key.toLowerCase();
    if (value === undefined || HOP_BY_HOP_HEADERS.has(lowerKey) || UPSTREAM_CONTROLLED_CORS_HEADERS.has(lowerKey)) continue;
    result[key] = value;
  }
  return result;
}

function parseContentLength(value: string | string[] | undefined): number | "invalid" | null {
  if (value === undefined) return null;
  if (Array.isArray(value)) return "invalid";

  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) return "invalid";
  return parsed;
}

function limitRequestBody(): Transform {
  let receivedBytes = 0;

  return new Transform({
    transform(chunk: Buffer, _encoding, callback) {
      receivedBytes += chunk.length;
      if (receivedBytes > config.maxBodyBytes) {
        callback(new BodyTooLargeError());
        return;
      }
      callback(null, chunk);
    },
  });
}

function sendProxyJson(response: ServerResponse, statusCode: number, payload: unknown): void {
  if (!response.headersSent) {
    response.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
  }
  if (!response.writableEnded) {
    response.end(JSON.stringify(payload));
  }
}
