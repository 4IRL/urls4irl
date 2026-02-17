/**
 * Security check: Redirect if head element is nearly empty (XSS protection)
 * Runs immediately on import - must be first import in entry points
 */
if (document.querySelector("head")?.childElementCount === 1) {
  window.location.href = "/";
}
