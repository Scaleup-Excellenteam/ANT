const $ = (selector) => document.querySelector(selector);

function message(target, text, error = false) {
  target.textContent = text;
  target.classList.toggle("error", error);
}

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}


function renderSatellite(status) {
  $("#sat-status").textContent = status.status;
  $("#sat-mode").textContent = status.mode;
  $("#sat-latency").textContent = `${status.latency_ms ?? "—"} ms`;
  $("#sat-cache").textContent = status.cached_records;
  $("#sat-pending").textContent = status.pending_operations;
  $("#sat-contact").textContent = status.last_successful_contact || "Never";
  const badge = $("#satellite-badge");
  badge.textContent = status.status;
  badge.className = `badge ${status.status.toLowerCase()}`;
}

async function refreshPending() {
  const data = await jsonRequest("/api/satellite/pending");
  $("#pending-output").textContent = JSON.stringify(data.operations, null, 2);
}

async function refreshCache() {
  const data = await jsonRequest("/api/satellite/cache");
  const terminalRecords = data.records.filter((record) => record.key.startsWith("terminal-query:"));
  $("#cache-output").textContent = JSON.stringify(terminalRecords, null, 2);
}

async function refreshSatellite() {
  try {
    const status = await jsonRequest("/api/satellite/status");
    renderSatellite(status);
    await Promise.all([refreshPending(), refreshCache()]);
  } catch (error) {
    message($("#satellite-message"), error.message, true);
  }
}

$("#disconnect").addEventListener("click", async () => {
  try {
    const status = await jsonRequest("/api/satellite/simulate-disconnect", {method: "POST"});
    renderSatellite(status);
    message($("#satellite-message"), "Simulation disconnected. Reads now use cached data; writes are queued.");
  } catch (error) { message($("#satellite-message"), error.message, true); }
});

$("#reconnect").addEventListener("click", async () => {
  message($("#satellite-message"), "RECOVERING: replaying pending operations…");
  try {
    const status = await jsonRequest("/api/satellite/reconnect", {method: "POST"});
    renderSatellite(status);
    await refreshPending();
    message($("#satellite-message"), "Recovery completed. The queue was synchronized in order.");
  } catch (error) {
    await refreshSatellite();
    message($("#satellite-message"), error.message, true);
  }
});

$("#set-latency").addEventListener("click", async () => {
  try {
    const status = await jsonRequest("/api/satellite/simulate-latency", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({latency_ms: Number($("#latency-input").value)}),
    });
    renderSatellite(status);
    message($("#satellite-message"), "Simulated latency updated.");
  } catch (error) { message($("#satellite-message"), error.message, true); }
});

$("#sat-read-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await jsonRequest(`/api/satellite/data/${encodeURIComponent($("#sat-read-key").value)}`);
    $("#sat-read-output").textContent = JSON.stringify(data.result, null, 2);
    renderSatellite(data.satellite);
  } catch (error) { $("#sat-read-output").textContent = error.message; }
});

$("#sat-write-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await jsonRequest("/api/satellite/data", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        key: $("#sat-write-key").value,
        value: {message: $("#sat-write-value").value, written_at: new Date().toISOString()},
      }),
    });
    $("#sat-write-output").textContent = JSON.stringify(data.operation, null, 2);
    renderSatellite(data.satellite);
    await refreshPending();
  } catch (error) { $("#sat-write-output").textContent = error.message; }
});

refreshSatellite();
setInterval(refreshSatellite, 3000);
