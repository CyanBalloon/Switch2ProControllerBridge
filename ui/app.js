/**
 * Bridge UI — called from Python via window.bridgeUI.setStatus(state, detail)
 */

const COPY = {
  scanning: {
    title: "Scanning",
    sub: "Hold SYNC to pair, or press any button to reconnect",
    btn: "Cancel",
  },
  idle: {
    title: "Ready",
    sub: "Press Start to scan for your controller",
    btn: "Start",
  },
  connecting: {
    title: "Connecting",
    sub: "Establishing secure session with your controller…",
    btn: "Cancel",
  },
  connected: {
    title: "Connected",
    sub: "Virtual Xbox 360 controller is active",
    btn: "Disconnect",
  },
  closing: {
    title: "Closing",
    sub: "Disconnecting controller…",
    btn: "Please wait",
  },
  error: {
    title: "Error",
    sub: "Something went wrong. Check the log folder for details.",
    btn: "Close",
  },
};

let pyBridge = null;
let uiState = "scanning";

function $(id) {
  return document.getElementById(id);
}

window.bridgeUI = {
  setStatus(state, detail = "") {
    uiState = state;
    document.body.dataset.state = state;
    const c = COPY[state] || COPY.scanning;

    $("status-title").textContent = c.title;
    $("status-sub").textContent = detail || c.sub;

    const btn = $("action-btn");
    btn.textContent = c.btn;
    btn.disabled = state === "closing";
  },

};

function onActionClick() {
  if (!pyBridge) return;

  if (uiState === "idle") {
    pyBridge.resumeScan();
  } else if (uiState === "connected") {
    pyBridge.disconnectSession();
  } else if (uiState === "error") {
    pyBridge.closeApp();
  } else if (uiState === "scanning" || uiState === "connecting") {
    pyBridge.pauseScan();
  }
}

function bindControls() {
  $("btn-close")?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (pyBridge) {
      pyBridge.closeApp();
    }
  });
  $("btn-min")?.addEventListener("click", () => {
    if (pyBridge) pyBridge.minimize();
  });
  $("action-btn")?.addEventListener("click", onActionClick);

  const dragHandle = $("titlebar");
  dragHandle?.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    if (e.target.closest("button, .card-controls")) return;
    if (pyBridge) pyBridge.drag();
  });
}

function initPyBridge() {
  if (typeof QWebChannel === "undefined" || typeof qt === "undefined") {
    console.error("QWebChannel unavailable");
    return;
  }
  new QWebChannel(qt.webChannelTransport, (channel) => {
    pyBridge = channel.objects.bridge;
    bindControls();
    window.bridgeUI.setStatus("scanning");
  });
}

document.addEventListener("DOMContentLoaded", initPyBridge);
