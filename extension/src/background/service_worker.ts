// Manages Ghost Mode ON/OFF state and browser action badge.

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ ghostMode: false, shieldlayerGatewayUrl: "http://localhost:8000" });
  chrome.action.setBadgeText({ text: "OFF" });
  chrome.action.setBadgeBackgroundColor({ color: "#71717a" });
});

chrome.action.onClicked.addListener(async () => {
  const result = await chrome.storage.local.get(["ghostMode"]);
  const newState = !result.ghostMode;
  await chrome.storage.local.set({ ghostMode: newState });
  chrome.action.setBadgeText({ text: newState ? "ON" : "OFF" });
  chrome.action.setBadgeBackgroundColor({ color: newState ? "#3b82f6" : "#71717a" });
});
