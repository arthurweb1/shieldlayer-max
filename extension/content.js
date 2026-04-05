(function () {
  'use strict';

  let ghostModeActive = false;
  let badgeTimer = null;

  const INPUT_SELECTOR = [
    'textarea',
    '[contenteditable="true"]',
    '[contenteditable=""]',
  ].join(', ');

  function createBadge() {
    const existing = document.getElementById('slm-badge');
    if (existing) return existing;

    const badge = document.createElement('div');
    badge.id = 'slm-badge';
    badge.textContent = 'ShieldLayer \u00b7 Ghost Mode';
    document.body.appendChild(badge);
    return badge;
  }

  function showBadge() {
    if (!ghostModeActive) return;
    const badge = createBadge();
    badge.classList.add('slm-badge-visible');

    if (badgeTimer) clearTimeout(badgeTimer);
    badgeTimer = setTimeout(() => {
      badge.classList.remove('slm-badge-visible');
    }, 2000);
  }

  function hideBadge() {
    const badge = document.getElementById('slm-badge');
    if (badge) badge.classList.remove('slm-badge-visible');
    if (badgeTimer) {
      clearTimeout(badgeTimer);
      badgeTimer = null;
    }
  }

  function attachInput(el) {
    if (el.dataset.slmBound === '1') return;
    el.dataset.slmBound = '1';

    el.addEventListener('focus', () => {
      if (!ghostModeActive) return;
      el.classList.add('slm-ghost-active');
      el.dataset.slm = 'protected';
      showBadge();
    });

    el.addEventListener('blur', () => {
      el.classList.remove('slm-ghost-active');
      delete el.dataset.slm;
      hideBadge();
    });
  }

  function scanInputs() {
    document.querySelectorAll(INPUT_SELECTOR).forEach(attachInput);
  }

  function applyGhostState(enabled) {
    ghostModeActive = enabled;
    if (!enabled) {
      document.querySelectorAll('.slm-ghost-active').forEach((el) => {
        el.classList.remove('slm-ghost-active');
        delete el.dataset.slm;
      });
      hideBadge();
    }
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        if (node.matches(INPUT_SELECTOR)) {
          attachInput(node);
        }
        node.querySelectorAll(INPUT_SELECTOR).forEach(attachInput);
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'GHOST_STATE') {
      applyGhostState(message.ghostMode);
    }
  });

  chrome.runtime.sendMessage({ type: 'PING' }, (response) => {
    if (chrome.runtime.lastError) return;
    if (response && response.type === 'PONG') {
      applyGhostState(response.ghostMode);
      scanInputs();
    }
  });
})();
