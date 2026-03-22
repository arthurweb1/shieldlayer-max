// ShieldLayer Max — Background Service Worker
// Validates license key against the API

const API_BASE = "https://shieldlayer.ai/api";

chrome.runtime.onInstalled.addListener(() => {
  console.log("[ShieldLayer] Extension installed");
  chrome.storage.sync.get("licenseKey", (data) => {
    if (!data.licenseKey) {
      chrome.storage.sync.set({ shieldActive: false, seats: 0, piiCount: 0 });
    }
  });
});

// Message handler from content script and popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "VALIDATE_LICENSE") {
    validateLicense(msg.key).then(sendResponse);
    return true; // keep channel open for async
  }
  if (msg.type === "GET_STATUS") {
    chrome.storage.sync.get(["licenseKey", "shieldActive", "piiCount", "licenseEmail", "seats"], sendResponse);
    return true;
  }
  if (msg.type === "PII_EVENT") {
    // Increment session counter
    chrome.storage.sync.get("piiCount", (data) => {
      chrome.storage.sync.set({ piiCount: (data.piiCount || 0) + msg.count });
    });
    sendResponse({ ok: true });
    return true;
  }
  if (msg.type === "CLEAR_LICENSE") {
    chrome.storage.sync.set({ licenseKey: null, shieldActive: false, licenseEmail: null, seats: 0 });
    sendResponse({ ok: true });
    return true;
  }
});

async function validateLicense(key) {
  try {
    const res = await fetch(`${API_BASE}/license/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    const data = await res.json();
    if (data.valid) {
      chrome.storage.sync.set({
        licenseKey: key,
        shieldActive: true,
        licenseEmail: data.email,
        seats: data.seats,
        org: data.org,
      });
      return { valid: true, email: data.email, seats: data.seats, org: data.org };
    } else {
      return { valid: false, error: data.error || "Invalid license key" };
    }
  } catch (err) {
    // Offline fallback — trust cached key for 24h
    return { valid: false, error: "Network error — check connection" };
  }
}
