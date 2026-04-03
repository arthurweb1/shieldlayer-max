// Injects a pulsing electric-blue glow border when Ghost Mode is active.
// Uses MV3 chrome.storage.local to read current state.

const GLOW_ID = "shieldlayer-glow-frame";

function applyGlow(active: boolean): void {
  let frame = document.getElementById(GLOW_ID);

  if (!active) {
    if (frame) frame.remove();
    return;
  }

  if (frame) return; // already injected

  frame = document.createElement("div");
  frame.id = GLOW_ID;
  frame.style.cssText = `
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 2147483647;
    border: 3px solid #3b82f6;
    box-shadow: 0 0 24px 4px rgba(59, 130, 246, 0.5), inset 0 0 24px 4px rgba(59, 130, 246, 0.15);
    animation: shieldlayer-pulse 2s ease-in-out infinite;
  `;

  // Inject keyframes
  const style = document.createElement("style");
  style.textContent = `
    @keyframes shieldlayer-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }
  `;
  document.head?.appendChild(style);
  document.body?.appendChild(frame);
}

// Read initial state
chrome.storage.local.get(["ghostMode"], (result) => {
  applyGlow(!!result.ghostMode);
});

// Listen for state changes
chrome.storage.onChanged.addListener((changes) => {
  if ("ghostMode" in changes) {
    applyGlow(!!changes.ghostMode.newValue);
  }
});
