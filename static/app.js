const scanButton = document.getElementById("scan-button");
const scanMessage = document.getElementById("scan-message");
const resultsContainer = document.getElementById("results-container");
const template = document.getElementById("paper-card-template");

const statChecked = document.getElementById("stat-checked");
const statInvalid = document.getElementById("stat-invalid");
const statPages = document.getElementById("stat-pages");
const generatedAt = document.getElementById("generated-at");

let pollTimer = null;

function setStats(results) {
  const summary = results?.summary;
  statChecked.textContent = summary?.checked_papers ?? 0;
  statInvalid.textContent = summary?.invalid_papers ?? 0;
  statPages.textContent = summary?.max_pages_scanned ?? 0;
  generatedAt.textContent = summary?.generated_at
    ? `Last result: ${summary.generated_at}`
    : "No results yet.";
}

function renderEmptyState(message) {
  resultsContainer.innerHTML = `<div class="empty-state">${message}</div>`;
}

function renderResults(results) {
  setStats(results);
  const invalidPapers = results?.invalid_papers ?? [];

  if (invalidPapers.length === 0) {
    renderEmptyState("No invalid papers were detected in the latest scan.");
    return;
  }

  resultsContainer.innerHTML = "";
  invalidPapers.forEach((paper) => {
    const node = template.content.cloneNode(true);
    node.querySelector(".score-chip").textContent = `score ${paper.match_score}`;
    node.querySelector(".paper-title").textContent = `${paper.subject_title} (${paper.course_code})`;
    node.querySelector(".paper-meta").textContent = `${paper.exam_type} | Slot ${paper.slot} | ${paper.year} | OCR page ${paper.ocr_page}`;
    node.querySelector(".listed-title").textContent = paper.listed_title;
    node.querySelector(".ocr-title").textContent = paper.ocr_title;
    node.querySelector(".reason").textContent = paper.reason;
    node.querySelector(".excerpt").textContent = paper.page_excerpt;

    const paperLink = node.querySelector(".paper-link");
    paperLink.href = paper.website_url;

    const pdfLink = node.querySelector(".pdf-link");
    pdfLink.href = paper.pdf_url;

    resultsContainer.appendChild(node);
  });
}

async function loadResults() {
  const response = await fetch("/api/results");
  const payload = await response.json();

  if (payload.results) {
    renderResults(payload.results);
  } else {
    setStats(null);
    renderEmptyState("Run the scanner to generate a review list.");
  }

  const scan = payload.scan;
  scanMessage.textContent = scan.error ? `${scan.message} ${scan.error}` : scan.message;
  scanButton.disabled = scan.status === "running";

  if (scan.status === "running" && scan.progress?.total) {
    scanMessage.textContent = `Scanning ${scan.progress.checked}/${scan.progress.total} papers. Invalid so far: ${scan.progress.invalid}.`;
  }

  if (scan.status === "running" && !pollTimer) {
    pollTimer = window.setInterval(async () => {
      await loadResults();
      const latest = await fetch("/api/results").then((res) => res.json());
      if (latest.scan.status !== "running" && pollTimer) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    }, 5000);
  }

  if (scan.status !== "running" && pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

scanButton.addEventListener("click", async () => {
  scanButton.disabled = true;
  scanMessage.textContent = "Starting scan...";

  const response = await fetch("/api/scan", { method: "POST" });
  if (!response.ok) {
    const payload = await response.json();
    scanMessage.textContent = payload.detail || "Could not start the scan.";
    scanButton.disabled = false;
    return;
  }

  await loadResults();
});

loadResults();
