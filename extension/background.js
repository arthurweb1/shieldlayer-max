const DEFAULT_STATE = {
  ghostMode: true,
  gatewayUrl: 'http://localhost:8000',
  sessionActive: false,
};

const AI_PLATFORM_PATTERN = /^https:\/\/(chat\.openai\.com|claude\.ai|gemini\.google\.com)\//;

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set(DEFAULT_STATE);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PING') {
    chrome.storage.local.get(['ghostMode'], (result) => {
      sendResponse({ type: 'PONG', ghostMode: result.ghostMode ?? true });
    });
    return true;
  }

  if (message.type === 'TOGGLE_GHOST') {
    chrome.storage.local.get(['ghostMode'], (result) => {
      const next = !result.ghostMode;
      chrome.storage.local.set({ ghostMode: next }, () => {
        chrome.tabs.query({}, (tabs) => {
          for (const tab of tabs) {
            if (tab.id && tab.url && AI_PLATFORM_PATTERN.test(tab.url)) {
              chrome.tabs.sendMessage(tab.id, { type: 'GHOST_STATE', ghostMode: next });
            }
          }
        });
        sendResponse({ ghostMode: next });
      });
    });
    return true;
  }
});
