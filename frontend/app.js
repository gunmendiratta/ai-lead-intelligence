const $ = (id) => document.getElementById(id);
let currentPlan = null;
let currentResult = null;

function showMessage(text, error = false) {
  const node = $("message");
  node.textContent = text;
  node.className = `message ${error ? "error" : ""}`;
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Request failed");
  return payload;
}

$("planButton").addEventListener("click", async () => {
  showMessage("Generating a constrained plan...");
  try {
    currentPlan = await postJson("/api/plan", {
      url: $("url").value,
      prompt: "Extract all available public business listing fields.",
      browser_mode: $("browser").checked,
      max_records: Number($("limit").value)
    });
    $("planPanel").classList.remove("hidden");
    $("planOutput").textContent = JSON.stringify(currentPlan, null, 2);
    $("warnings").innerHTML = (currentPlan.warnings || []).map((warning) => `<p>${warning}</p>`).join("");
    $("runButton").disabled = false;
    $("planStatus").textContent = "Ready for approval";
    showMessage("Review the selectors and approve the plan to run it.");
  } catch (error) {
    showMessage(error.message, true);
  }
});

$("runButton").addEventListener("click", async () => {
  if (!currentPlan) return;
  showMessage("Running the approved extraction plan...");
  $("runButton").disabled = true;
  try {
    currentResult = await postJson("/api/execute", { plan: currentPlan });
    renderResults(currentResult.records || []);
    showMessage(`Completed. ${currentResult.record_count} records returned.`);
    await generateLeads();
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    $("runButton").disabled = false;
  }
});

function renderResults(records) {
  $("resultsPanel").classList.remove("hidden");
  $("count").textContent = `${records.length} records`;
  const columns = [...new Set(records.flatMap((record) => Object.keys(record)))];
  $("tableHead").innerHTML = `<tr>${columns.map((column) => `<th>${column}</th>`).join("")}</tr>`;
  $("tableBody").innerHTML = records.map((record) => `<tr>${columns.map((column) => `<td>${record[column] || ""}</td>`).join("")}</tr>`).join("");
}

function renderSmallResult(targetId, title, records, downloadName) {
  const target = $(targetId);
  target.classList.remove("hidden");
  target.innerHTML = `<p><strong>${title}:</strong> ${records.length}</p><button class="inline-download">Download ${downloadName}</button>`;
  target.querySelector("button").addEventListener("click", () => download(downloadName, JSON.stringify(records, null, 2), "application/json"));
}

function renderLeadResult(result) {
  const target = $("leadResult");
  target.classList.remove("hidden");
  const records = result.records || [];
  const contacts = result.contacts || [];
  const columns = ["business_name", "city", "places_business_name", "places_business_address", "places_overall_similarity", "places_verification_status", "verified_public_phone", "verified_public_email"];
  target.innerHTML = `<p><strong>Lead matches:</strong> ${records.length} &nbsp; <strong>Contact leads:</strong> ${contacts.length}</p><div class="table-wrap"><table><thead><tr>${columns.map((column) => `<th>${column}</th>`).join("")}</tr></thead><tbody>${contacts.map((record) => `<tr>${columns.map((column) => `<td>${record[column] || ""}</td>`).join("")}</tr>`).join("")}</tbody></table></div><button class="inline-download">Download verified contacts</button>`;
  target.querySelector("button").addEventListener("click", () => download("verified_contacts.json", JSON.stringify(contacts, null, 2), "application/json"));
}

$("commandButton").addEventListener("click", async () => {
  const records = currentResult?.records || [];
  if (!records.length) return showMessage("There are no extracted records to prompt.", true);
  try {
    const result = await postJson("/api/records/command", { records, prompt: $("recordPrompt").value });
    renderSmallResult("commandResult", "Kept records", result.kept, "filtered_records.json");
    showMessage(`Prompt applied: ${result.kept.length} kept, ${result.excluded.length} excluded.`);
  } catch (error) { showMessage(error.message, true); }
});

$("leadButton").addEventListener("click", async () => {
  await generateLeads();
});

async function generateLeads() {
  const records = currentResult?.records || [];
  if (!records.length) return showMessage("There are no extracted records to generate leads from.", true);
  try {
    const result = await postJson("/api/leads/generate", {
      records,
      name_field: $("nameField").value,
      address_field: $("addressField").value
    });
    renderLeadResult(result);
    showMessage(`Lead generation completed: ${result.contact_count} contact leads returned.`);
  } catch (error) { showMessage(error.message, true); }
}

function download(filename, content, type) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

$("downloadJson").addEventListener("click", () => download("leads.json", JSON.stringify(currentResult, null, 2), "application/json"));
$("downloadCsv").addEventListener("click", () => {
  const records = currentResult?.records || [];
  const columns = [...new Set(records.flatMap((record) => Object.keys(record)))];
  const csv = [columns, ...records.map((record) => columns.map((column) => `"${String(record[column] || "").replaceAll('"', '""')}"`))]
    .map((row) => row.join(","))
    .join("\n");
  download("leads.csv", csv, "text/csv");
});
