const folderPathEl = document.getElementById("folderPath");
const browseBtn = document.getElementById("browseBtn");
const reverseGeocodeEl = document.getElementById("reverseGeocode");
const createMapEl = document.getElementById("createMap");
const scanBtn = document.getElementById("scanBtn");
const exportBtn = document.getElementById("exportBtn");
const exportExcelBtn = document.getElementById("exportExcelBtn");
const clearBtn = document.getElementById("clearBtn");
const statusText = document.getElementById("statusText");
const resultsBody = document.querySelector("#resultsTable tbody");
const logBox = document.getElementById("logBox");
const stats = document.getElementById("stats");
const totalFiles = document.getElementById("totalFiles");
const withGps = document.getElementById("withGps");
const withoutGps = document.getElementById("withoutGps");
const dropZone = document.getElementById("dropZone");
const previewGrid = document.getElementById("previewGrid");

function log(message) {
  const now = new Date().toLocaleTimeString();
  logBox.textContent += `[${now}] ${message}\n`;
  logBox.scrollTop = logBox.scrollHeight;
}

function clearResults() {
  resultsBody.innerHTML = "";
  logBox.textContent = "";
  stats.hidden = true;
  totalFiles.textContent = "0";
  withGps.textContent = "0";
  withoutGps.textContent = "0";
  statusText.textContent = "Ready.";
  previewGrid.innerHTML = "";
}

function statusClass(status) {
  const text = (status || "").toLowerCase();
  if (text.includes("extracted")) return "badge-ok";
  if (text.includes("error") || text.includes("corrupted") || text.includes("unsupported")) return "badge-error";
  return "badge-warn";
}

function addRow(row) {
  const tr = document.createElement("tr");
  
  // Format location with Google Maps link if coords exist
  let locationHtml = row.location_name ?? "";
  if (row.latitude && row.longitude) {
    const mapsLink = `https://www.google.com/maps?q=${row.latitude},${row.longitude}`;
    locationHtml = `
      <a href="${mapsLink}" target="_blank" class="map-link" title="Open in Google Maps">
        ${locationHtml || "View Map"}
      </a>
    `;
  }

  tr.innerHTML = `
    <td>${row.image_name ?? ""}</td>
    <td>${row.latitude ?? ""}</td>
    <td>${row.longitude ?? ""}</td>
    <td>${row.timestamp ?? ""}</td>
    <td class="${statusClass(row.status)}">${row.status ?? ""}</td>
    <td>${locationHtml}</td>
    <td>${row.error ?? ""}</td>
  `;
  resultsBody.appendChild(tr);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Request failed with ${response.status}`);
  }

  return response;
}

browseBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/browse-folder");
    const data = await response.json();
    if (data.folder_path) {
      folderPathEl.value = data.folder_path;
    }
  } catch (err) {
    console.error("Failed to open folder picker", err);
  }
});

scanBtn.addEventListener("click", async () => {
  clearResults();

  const payload = {
    folder_path: folderPathEl.value.trim(),
    reverse_geocode: reverseGeocodeEl.checked,
    create_map: createMapEl.checked,
  };

  if (!payload.folder_path) {
    alert("Please enter a folder path.");
    return;
  }

  try {
    statusText.textContent = "Scanning...";
    log(`Scanning folder: ${payload.folder_path}`);

    const response = await postJson("/api/scan", payload);
    const data = await response.json();

    stats.hidden = false;
    totalFiles.textContent = String(data.total_files ?? 0);
    withGps.textContent = String(data.with_gps ?? 0);
    withoutGps.textContent = String(data.without_gps ?? 0);

    (data.results || []).forEach(addRow);

    if (data.map_file) {
      log(`Map generated: ${data.map_file}`);
    }
    log(`Scan completed. Total: ${data.total_files}, With GPS: ${data.with_gps}, Without GPS: ${data.without_gps}`);
    statusText.textContent = "Completed.";
  } catch (error) {
    console.error(error);
    statusText.textContent = "Failed.";
    log(`Error: ${error.message}`);
    alert(`Scan failed. ${error.message}`);
  }
});

exportBtn.addEventListener("click", async () => {
  const payload = {
    folder_path: folderPathEl.value.trim(),
    reverse_geocode: reverseGeocodeEl.checked,
    create_map: createMapEl.checked,
  };

  if (!payload.folder_path) {
    alert("Please enter a folder path.");
    return;
  }

  try {
    statusText.textContent = "Exporting CSV...";
    log(`Exporting CSV for folder: ${payload.folder_path}`);

    const response = await postJson("/api/export-csv", payload);
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^\"]+)"?/i);
    const filename = match ? match[1] : "gps_results.csv";

    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(downloadUrl);

    statusText.textContent = "CSV exported.";
    log(`CSV downloaded: ${filename}`);
  } catch (error) {
    console.error(error);
    statusText.textContent = "Export failed.";
    log(`Error: ${error.message}`);
    alert(`CSV export failed. ${error.message}`);
  }
});

exportExcelBtn.addEventListener("click", async () => {
  const payload = {
    folder_path: folderPathEl.value.trim(),
    reverse_geocode: reverseGeocodeEl.checked,
    create_map: createMapEl.checked,
  };

  if (!payload.folder_path) {
    alert("Please enter a folder path.");
    return;
  }

  try {
    statusText.textContent = "Exporting Excel...";
    log(`Exporting Excel for folder: ${payload.folder_path}`);

    const response = await postJson("/api/export-excel", payload);
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^\"]+)"?/i);
    const filename = match ? match[1] : `gps_results_${new Date().getTime()}.xlsx`;

    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(downloadUrl);

    statusText.textContent = "Excel exported.";
    log(`Excel downloaded: ${filename}`);
  } catch (error) {
    console.error(error);
    statusText.textContent = "Export failed.";
    log(`Error: ${error.message}`);
    alert(`Excel export failed. ${error.message}`);
  }
});

clearBtn.addEventListener("click", clearResults);
