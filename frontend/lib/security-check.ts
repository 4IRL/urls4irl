/**
 * Security check: Redirect if head element is nearly empty (XSS protection)
 * Runs immediately on import - must be first import in entry points
 */
import { debug } from "./debug.js";

const log = debug("security");

if (document.querySelector("head")?.childElementCount === 1) {
  log("head element has <=1 child — redirecting to /", {
    childElementCount: document.querySelector("head")?.childElementCount,
  });
  window.location.href = "/";
}
