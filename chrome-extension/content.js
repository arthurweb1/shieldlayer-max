// ShieldLayer Max — Content Script
// Intercepts text inputs, detects PII patterns, masks before submission

const CYBER_LIME = "#DFFF00";

// PII regex patterns (client-side, no server call needed)
const PII_PATTERNS = [
  { type: "EMAIL_ADDRESS",  regex: /\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b/g },
  { type: "IBAN",           regex: /\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b/g },
  { type: "PHONE",          regex: /(\+?\d[\d\s\-\(\)]{7,}\d)/g },
  { type: "PERSON",         regex: /\b([A-Z][a-z]+ [A-Z][a-z]+)\b/g },
  { type: "CREDIT_CARD",    regex: /\b(?:\d[ -]?){13,19}\b/g },
  { type: "DATE_OF_BIRTH",  regex: /\b\d{1,2}[.\/\-]\d{1,2}[.\/\-]\d{2,4}\b/g },
];

let shieldActive = false;
let counters = {};

// Check activation status
chrome.storage.sync.get(["shieldActive"], (data) => {
  shieldActive = data.shieldActive || false;
  if (shieldActive) init();
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.shieldActive) {
    shieldActive = changes.shieldActive.newValue;
    if (shieldActive) init();
  }
});

function init() {
  // Watch all textareas and contenteditable divs
  document.addEventListener("keydown", onKeyDown, true);
  observeNewInputs();
}

function observeNewInputs() {
  const observer = new MutationObserver(() => {
    document.querySelectorAll("textarea, [contenteditable='true']").forEach(attachToInput);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  document.querySelectorAll("textarea, [contenteditable='true']").forEach(attachToInput);
}

const attachedInputs = new WeakSet();
function attachToInput(el) {
  if (attachedInputs.has(el)) return;
  attachedInputs.add(el);
  el.addEventListener("input", () => checkForPII(el));
}

function onKeyDown(e) {
  // Intercept Enter/Return on chat inputs
  if (e.key === "Enter" && !e.shiftKey) {
    const target = e.target;
    if (target.tagName === "TEXTAREA" || target.contentEditable === "true") {
      const text = target.value || target.innerText || "";
      const matches = detectPII(text);
      if (matches.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        triggerMaskingFlow(target, matches, text);
      }
    }
  }
}

function detectPII(text) {
  const found = [];
  const countersLocal = {};
  for (const { type, regex } of PII_PATTERNS) {
    const matches = [...text.matchAll(new RegExp(regex.source, regex.flags))];
    if (matches.length > 0) {
      countersLocal[type] = (countersLocal[type] || 0) + matches.length;
      found.push({ type, matches: matches.map((m) => m[0]) });
    }
  }
  return found;
}

function checkForPII(el) {
  const text = el.value || el.innerText || "";
  const matches = detectPII(text);
  if (matches.length > 0) {
    showMiniBadge(el, matches.length);
  } else {
    hideMiniBadge(el);
  }
}

function triggerMaskingFlow(el, piiEntities, originalText) {
  showScanlineOverlay(el, () => {
    const { maskedText, entityMap } = maskText(originalText, piiEntities);
    if (el.tagName === "TEXTAREA") {
      el.value = maskedText;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      el.innerText = maskedText;
    }
    showTooltip(el, entityMap);
    // Report to background
    const totalCount = piiEntities.reduce((s, e) => s + e.matches.length, 0);
    chrome.runtime.sendMessage({ type: "PII_EVENT", count: totalCount });
    // After mask — wait 1.5s then submit
    setTimeout(() => {
      hideTooltip();
      simulateEnter(el);
    }, 1500);
  });
}

function maskText(text, piiEntities) {
  let masked = text;
  const entityMap = [];
  const counters = {};
  for (const { type, matches } of piiEntities) {
    for (const original of matches) {
      if (!masked.includes(original)) continue;
      counters[type] = (counters[type] || 0) + 1;
      const placeholder = `[${type}_${counters[type]}]`;
      masked = masked.replace(original, placeholder);
      entityMap.push({ type, original, placeholder });
    }
  }
  return { maskedText: masked, entityMap };
}

function simulateEnter(el) {
  el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  el.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", bubbles: true }));
}

// ──────────────────────────────────────────────────
// UI: Scanline overlay
// ──────────────────────────────────────────────────
function showScanlineOverlay(el, onComplete) {
  const rect = el.getBoundingClientRect();
  const overlay = document.createElement("div");
  overlay.id = "sl-scanline-overlay";
  overlay.style.cssText = `
    position: fixed;
    top: ${rect.top + window.scrollY}px;
    left: ${rect.left}px;
    width: ${rect.width}px;
    height: ${rect.height}px;
    pointer-events: none;
    z-index: 2147483647;
    overflow: hidden;
  `;
  const beam = document.createElement("div");
  beam.id = "sl-beam";
  beam.style.cssText = `
    position: absolute;
    left: 0; right: 0; top: -2px;
    height: 2px;
    background: ${CYBER_LIME};
    box-shadow: 0 0 8px 2px ${CYBER_LIME}, 0 0 20px 4px rgba(223,255,0,0.4);
    transition: top 0.75s ease-in;
  `;
  overlay.appendChild(beam);
  document.body.appendChild(overlay);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      beam.style.top = `${rect.height}px`;
    });
  });
  setTimeout(() => {
    overlay.remove();
    onComplete();
  }, 800);
}

// ──────────────────────────────────────────────────
// UI: PII Tooltip
// ──────────────────────────────────────────────────
function showTooltip(el, entityMap) {
  hideTooltip();
  const rect = el.getBoundingClientRect();
  const tip = document.createElement("div");
  tip.id = "sl-tooltip";
  tip.innerHTML = `
    <div style="padding:10px 14px;border-bottom:1px solid rgba(223,255,0,0.15);display:flex;align-items:center;justify-content:space-between;">
      <span style="font-family:monospace;font-size:11px;font-weight:700;color:${CYBER_LIME};letter-spacing:0.15em;text-transform:uppercase;">⚠ PII Detected</span>
      <span style="font-family:monospace;font-size:9px;color:rgba(248,248,248,0.4);letter-spacing:0.12em;text-transform:uppercase;">■ Masking complete</span>
    </div>
    <div style="padding:10px 14px;">
      ${entityMap.map(({ type, original, placeholder }) => `
        <div style="display:flex;align-items:center;gap:8px;font-family:monospace;font-size:11px;margin-bottom:5px;">
          <span style="color:${CYBER_LIME};min-width:120px;font-size:10px;">${type}</span>
          <span style="color:rgba(248,248,248,0.25);text-decoration:line-through;font-size:10px;">${original.substring(0,20)}${original.length>20?"…":""}</span>
          <span style="color:rgba(248,248,248,0.2);margin:0 4px;">→</span>
          <span style="color:#fff;border:1px solid rgba(248,248,248,0.12);padding:1px 6px;background:rgba(255,255,255,0.03);font-size:10px;">${placeholder}</span>
        </div>
      `).join("")}
    </div>
  `;
  tip.style.cssText = `
    position: fixed;
    top: ${Math.max(8, rect.top - 10)}px;
    left: ${rect.left}px;
    width: ${Math.min(480, rect.width)}px;
    transform: translateY(-100%);
    background: rgba(13,13,13,0.95);
    border: 1px solid ${CYBER_LIME};
    box-shadow: 0 0 0 1px rgba(223,255,0,0.08), 0 12px 40px rgba(0,0,0,0.9), inset 0 0 30px rgba(223,255,0,0.03);
    z-index: 2147483647;
    backdrop-filter: blur(12px);
    animation: sl-fade-in 0.2s ease;
  `;
  document.body.appendChild(tip);
}

function hideTooltip() {
  document.getElementById("sl-tooltip")?.remove();
}

// ──────────────────────────────────────────────────
// UI: Mini badge on input
// ──────────────────────────────────────────────────
const badgeMap = new WeakMap();
function showMiniBadge(el, count) {
  if (badgeMap.has(el)) {
    badgeMap.get(el).textContent = `⚠ ${count} PII`;
    return;
  }
  const rect = el.getBoundingClientRect();
  const badge = document.createElement("div");
  badge.textContent = `⚠ ${count} PII`;
  badge.style.cssText = `
    position: fixed;
    top: ${rect.top + 4}px;
    right: ${window.innerWidth - rect.right + 4}px;
    background: rgba(13,13,13,0.9);
    border: 1px solid ${CYBER_LIME};
    color: ${CYBER_LIME};
    font-family: monospace;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.12em;
    padding: 2px 8px;
    z-index: 2147483646;
    pointer-events: none;
  `;
  document.body.appendChild(badge);
  badgeMap.set(el, badge);
}

function hideMiniBadge(el) {
  if (badgeMap.has(el)) {
    badgeMap.get(el).remove();
    badgeMap.delete(el);
  }
}
