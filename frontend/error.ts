import "./lib/security-check.js";

// Refresh button handler - removes hash and reloads
const refreshBtn = document.getElementById("refreshBtn");
if (refreshBtn) {
  refreshBtn.addEventListener("click", () => {
    window.location.href = window.location.href.split("#")[0];
  });
}
