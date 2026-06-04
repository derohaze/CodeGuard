import http from "node:http";
import https from "node:https";
import type { IncomingHttpHeaders, IncomingMessage, RequestOptions, ServerResponse } from "node:http";
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

export function proxyToPython(request: IncomingMessage, response: ServerResponse, requestUrl: URL): void {
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

  const upstreamRequest = transport.request(options, (upstreamResponse) => {
    response.writeHead(upstreamResponse.statusCode ?? 502, filterResponseHeaders(upstreamResponse.headers));
    upstreamResponse.pipe(response);
  });

  upstreamRequest.on("error", () => {
    logProxyError(request.method ?? "GET", requestUrl.pathname);
    if (!response.headersSent) {
      response.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    }
    response.end(JSON.stringify({ detail: "Python security API is unavailable." }));
  });

  request.pipe(upstreamRequest);
}

function buildProxyHeaders(headers: IncomingHttpHeaders): Record<string, string | string[]> {
  const result: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (value === undefined || HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
    result[key] = value;
  }
  result["x-forwarded-host"] = String(headers.host ?? "");
  result["x-forwarded-proto"] = "http";
  return result;
}

function filterResponseHeaders(headers: IncomingHttpHeaders): Record<string, string | string[]> {
  const result: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (value === undefined || HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
    result[key] = value;
  }
  result["access-control-allow-origin"] = "*";
  result["access-control-allow-methods"] = "GET,POST,PATCH,DELETE,OPTIONS";
  result["access-control-allow-headers"] = "Content-Type,Authorization";
  return result;
}
