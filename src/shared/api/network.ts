const STARTUP_RETRY_DELAYS_MS = [300, 700, 1500, 2500];
const STARTUP_READY_PATH = "/api/v1/health/live";

let startupReadyPromise: Promise<void> | null = null;
let startupReadyOrigin: string | null = null;

function normalizeMethod(method?: string): string {
  return (method ?? "GET").toUpperCase();
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function resolveUrl(input: RequestInfo | URL): URL | null {
  if (input instanceof URL) {
    return input;
  }
  if (typeof input === "string") {
    return new URL(input, globalThis.location?.href);
  }
  if (typeof Request !== "undefined" && input instanceof Request) {
    return new URL(input.url, globalThis.location?.href);
  }
  return null;
}

function shouldProbeApi(url: URL | null): boolean {
  if (!url) return false;
  return url.pathname.startsWith("/api/v1/") && url.pathname !== STARTUP_READY_PATH;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (!signal) {
    return new Promise((resolve) => {
      globalThis.setTimeout(resolve, ms);
    });
  }

  if (signal.aborted) {
    return Promise.reject(new DOMException("The operation was aborted.", "AbortError"));
  }

  return new Promise((resolve, reject) => {
    const timer = globalThis.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);

    const onAbort = () => {
      globalThis.clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("The operation was aborted.", "AbortError"));
    };

    signal.addEventListener("abort", onAbort, { once: true });
  });
}

async function waitForApiStartup(url: URL | null, signal?: AbortSignal): Promise<void> {
  if (!shouldProbeApi(url)) {
    return;
  }

  const origin = url.origin;
  if (startupReadyOrigin === origin && startupReadyPromise) {
    return startupReadyPromise;
  }

  startupReadyOrigin = origin;
  startupReadyPromise = (async () => {
    const healthUrl = new URL(STARTUP_READY_PATH, origin);
    const attempts = STARTUP_RETRY_DELAYS_MS.length + 1;

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        const response = await fetch(healthUrl, { method: "GET", signal });
        if (response.ok) {
          return;
        }
      } catch (error) {
        if (isAbortError(error) || attempt === attempts - 1) {
          throw error;
        }
      }

      if (attempt < attempts - 1) {
        await sleep(STARTUP_RETRY_DELAYS_MS[attempt], signal);
      }
    }

    throw new Error("API startup probe failed.");
  })().catch((error) => {
    startupReadyPromise = null;
    startupReadyOrigin = null;
    throw error;
  });

  return startupReadyPromise;
}

export async function fetchWithStartupRetry(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const method = normalizeMethod(init?.method);
  const shouldRetry = method === "GET";
  const attempts = shouldRetry ? STARTUP_RETRY_DELAYS_MS.length + 1 : 1;
  const url = resolveUrl(input);

  if (shouldRetry) {
    await waitForApiStartup(url, init?.signal);
  }

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await fetch(input, init);
    } catch (error) {
      if (!shouldRetry || isAbortError(error) || attempt === attempts - 1) {
        throw error;
      }

      await sleep(STARTUP_RETRY_DELAYS_MS[attempt], init?.signal);
    }
  }

  throw new Error("Startup retry loop exited unexpectedly.");
}
