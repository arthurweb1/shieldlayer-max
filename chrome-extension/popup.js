// Popup logic — communicates with background service worker

async function init() {
  const status = await new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "GET_STATUS" }, resolve);
  });

  if (status?.shieldActive && status?.licenseKey) {
    showActiveState(status);
  } else {
    showInactiveState();
  }
}

function showActiveState(status) {
  document.getElementById("statusDot").classList.add("active");
  document.getElementById("statusValue").textContent = "SHIELD ACTIVE";
  document.getElementById("statusValue").classList.remove("inactive");
  document.getElementById("statusMeta").textContent =
    `${status.licenseEmail || "Licensed"} · ${status.seats || 1} seat(s)`;
  document.getElementById("statsRow").style.display = "grid";
  document.getElementById("statPii").textContent = status.piiCount || 0;
  document.getElementById("statSeats").textContent = status.seats || 1;
  document.getElementById("shieldToggle").style.display = "flex";
  document.getElementById("licenseForm").style.display = "none";
  document.getElementById("activeActions").style.display = "block";
}

function showInactiveState() {
  document.getElementById("statusDot").classList.remove("active");
  document.getElementById("statusValue").textContent = "NOT ACTIVATED";
  document.getElementById("statusValue").classList.add("inactive");
  document.getElementById("statusMeta").textContent = "Enter your license key below";
  document.getElementById("statsRow").style.display = "none";
  document.getElementById("shieldToggle").style.display = "none";
  document.getElementById("licenseForm").style.display = "block";
  document.getElementById("activeActions").style.display = "none";
}

async function activate() {
  const key = document.getElementById("keyInput").value.trim();
  if (!key) {
    showError("Please enter a license key");
    return;
  }
  showError("");
  document.querySelector(".btn-primary").textContent = "Validating…";

  const result = await new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "VALIDATE_LICENSE", key }, resolve);
  });

  if (result?.valid) {
    showSuccess(`✓ Activated for ${result.email}`);
    setTimeout(() => {
      showActiveState({ ...result, licenseKey: key, piiCount: 0 });
      document.querySelector(".btn-primary").textContent = "▶ Activate License";
    }, 800);
  } else {
    showError(result?.error || "Invalid license key");
    document.querySelector(".btn-primary").textContent = "▶ Activate License";
  }
}

async function deactivate() {
  await new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "CLEAR_LICENSE" }, resolve);
  });
  showInactiveState();
}

function toggleShield() {
  chrome.storage.sync.get("shieldActive", (data) => {
    const newState = !data.shieldActive;
    chrome.storage.sync.set({ shieldActive: newState });
    const sw = document.getElementById("toggleSwitch");
    if (newState) { sw.classList.add("on"); }
    else { sw.classList.remove("on"); }
  });
}

function showError(msg) {
  const el = document.getElementById("errorMsg");
  el.textContent = msg;
  el.style.display = msg ? "block" : "none";
  document.getElementById("successMsg").style.display = "none";
}

function showSuccess(msg) {
  const el = document.getElementById("successMsg");
  el.textContent = msg;
  el.style.display = msg ? "block" : "none";
  document.getElementById("errorMsg").style.display = "none";
}

document.addEventListener("DOMContentLoaded", init);
