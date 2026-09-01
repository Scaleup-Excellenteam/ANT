const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const contextInput = document.querySelector("#context");
const contextRow = document.querySelector("#context-row");
const searchButton = document.querySelector("#search-button");
const loading = document.querySelector("#loading");
const statusBox = document.querySelector("#status");
const resultsBox = document.querySelector("#results");
const modeButtons = Array.from(document.querySelectorAll(".mode-tab"));

let currentMode = "english";

function setMode(mode) {
  currentMode = mode;
  modeButtons.forEach((button) => {
    const isActive = button.dataset.mode === mode;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  contextRow.classList.toggle("hidden", mode !== "gemini");
}

function setLoading(isLoading) {
  searchButton.disabled = isLoading;
  loading.classList.toggle("hidden", !isLoading);
}

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function clearResults(message = "No results.") {
  resultsBox.className = "results empty";
  resultsBox.textContent = message;
}

function renderResults(data) {
  resultsBox.className = "results";
  resultsBox.innerHTML = "";

  if (!data.results || data.results.length === 0) {
    clearResults("No results found.");
    return;
  }

  for (const [index, item] of data.results.entries()) {
    const card = document.createElement("article");
    card.className = "result-card";

    if (data.mode === "english") {
      card.innerHTML = `
        <p class="sentence">${escapeHtml(`${index + 1}. ${item.sentence.trimStart()}`)}</p>
        <div class="meta">
          <span>Score: ${escapeHtml(String(item.score))}</span>
          <span>Source: ${escapeHtml(item.source)}</span>
          <span>Offset: ${escapeHtml(String(item.offset))}</span>
        </div>
      `;
    } else {
      card.innerHTML = `
        <p class="ai-text">${escapeHtml(`${index + 1}. ${item.text}`)}</p>
        <div class="meta">
          <span class="badge ai">AI-GENERATED</span>
        </div>
      `;
    }

    resultsBox.appendChild(card);
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = queryInput.value.trim();
  if (!query) {
    clearResults();
    setStatus("Please enter some text.", true);
    return;
  }

  setLoading(true);
  setStatus("Searching...");
  clearResults("");

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        query,
        mode: currentMode,
        context: contextInput.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      clearResults();
      setStatus(data.error || "Search failed.", true);
      return;
    }

    renderResults(data);
    const gemini = data.gemini_ms === undefined ? "" : `; Gemini ${data.gemini_ms} ms`;
    const noun = data.mode === "gemini" ? "AI-generated suggestions" : "results";
    setStatus(`${data.count} ${noun} found in ${data.elapsed_ms} ms${gemini}`);
  } catch (error) {
    clearResults();
    setStatus(`Request failed: ${error.message}`, true);
  } finally {
    setLoading(false);
  }
});

setMode("english");
