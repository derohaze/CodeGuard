import http, { type IncomingMessage, type ServerResponse } from "node:http";
import { config } from "./config.js";
import { logRequest, logStartup } from "./logger.js";
import { proxyToPython } from "./proxy.js";

const server = http.createServer((request, response) => {
  const startedAt = performance.now();
  setCorsHeaders(response);

  if (request.method === "OPTIONS") {
    response.on("finish", () => logAccess(request, response, startedAt, "gateway"));
    response.writeHead(204);
    response.end();
    return;
  }

  const requestUrl = new URL(request.url ?? "/", `http://${request.headers.host ?? `${config.host}:${config.port}`}`);

  if (requestUrl.pathname === "/api/v1/gateway/health") {
    response.on("finish", () => logAccess(request, response, startedAt, "gateway"));
    sendJson(response, 200, {
      status: "ok",
      service: "node-security-gateway",
      python_api_base_url: config.pythonApiBaseUrl,
      owned_surfaces: ["security-api-proxy"],
    });
    return;
  }

  if (requestUrl.pathname.startsWith("/api/v1/")) {
    response.on("finish", () => logAccess(request, response, startedAt, "python-api"));
    proxyToPython(request, response, requestUrl);
    return;
  }

  response.on("finish", () => logAccess(request, response, startedAt, "gateway"));
  sendJson(response, 404, { detail: "Route not found." });
});

server.listen(config.port, config.host, () => {
  logStartup(`listening on http://${config.host}:${config.port}`);
  logStartup(`proxying security API to ${config.pythonApiBaseUrl}`);
});

function setCorsHeaders(response: ServerResponse): void {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type,Authorization");
}

function sendJson(response: ServerResponse, statusCode: number, payload: unknown): void {
  response.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}

function logAccess(
  request: IncomingMessage,
  response: ServerResponse,
  startedAt: number,
  target: "gateway" | "python-api",
): void {
  logRequest({
    method: request.method ?? "GET",
    path: request.url ?? "/",
    statusCode: response.statusCode,
    durationMs: performance.now() - startedAt,
    target,
  });
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

function shutdown(): void {
  server.close(() => {
    process.exit(0);
  });
}
