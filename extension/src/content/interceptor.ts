// Patches window.fetch to route OpenAI/Anthropic calls through ShieldLayer gateway.

const INTERCEPTED_HOSTS = [
  "api.openai.com",
  "api.anthropic.com",
];

const GATEWAY_KEY = "shieldlayerGatewayUrl";
const ENABLED_KEY = "ghostMode";

let gatewayUrl = "http://localhost:8000";
let ghostModeActive = false;

// Load config from storage
chrome.storage.local.get([GATEWAY_KEY, ENABLED_KEY], (result) => {
  if (result[GATEWAY_KEY]) gatewayUrl = result[GATEWAY_KEY] as string;
  ghostModeActive = !!result[ENABLED_KEY];
});

// Track live changes
chrome.storage.onChanged.addListener((changes) => {
  if (GATEWAY_KEY in changes) gatewayUrl = changes[GATEWAY_KEY].newValue as string;
  if (ENABLED_KEY in changes) ghostModeActive = !!changes[ENABLED_KEY].newValue;
});

const originalFetch = window.fetch.bind(window);

window.fetch = function (input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (!ghostModeActive) return originalFetch(input, init);

  const url = typeof input === "string"
    ? input
    : input instanceof URL
    ? input.href
    : (input as Request).url;

  const shouldIntercept = INTERCEPTED_HOSTS.some((host) => url.includes(host));
  if (!shouldIntercept) return originalFetch(input, init);

  // Rewrite URL: replace upstream host with gateway
  const rewritten = url
    .replace("https://api.openai.com", gatewayUrl)
    .replace("https://api.anthropic.com", gatewayUrl);

  const newInput = typeof input === "string"
    ? rewritten
    : input instanceof URL
    ? new URL(rewritten)
    : new Request(rewritten, input as Request);

  // Add gateway tracing header
  const headers = new Headers((init?.headers as HeadersInit | undefined) ?? {});
  headers.set("X-ShieldLayer-Source", "ghost-mode");

  return originalFetch(newInput, { ...init, headers });
};
