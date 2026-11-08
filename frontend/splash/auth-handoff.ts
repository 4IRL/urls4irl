import { getForwardableNextQuery } from "./next-param.js";
import { loginModalOpener, registerModalOpener } from "./init.js";

const OAUTH_ANCHOR_SELECTORS = [
  "#GoogleOAuthLogin",
  "#GitHubOAuthLogin",
  "#GoogleOAuthRegister",
  "#GitHubOAuthRegister",
] as const;

const OTHER_MODAL_PENDING_SELECTOR =
  "#ModalForm[data-modal-type], #ModalForm[data-modal-context], #ConfirmEmailModal[data-resend-token]";

/** Forward the page's single `next` onto every present OAuth anchor. */
export function applyNextToOAuthLinks(): void {
  const query = getForwardableNextQuery(window.location.search);
  if (query === null) return;
  const nextValue = new URLSearchParams(query).get("next") ?? "";

  for (const selector of OAUTH_ANCHOR_SELECTORS) {
    const anchor = document.querySelector<HTMLAnchorElement>(selector);
    const href = anchor?.getAttribute("href");
    if (!anchor || !href) continue;
    const url = new URL(href, window.location.origin);
    url.searchParams.set("next", nextValue);
    anchor.setAttribute("href", url.pathname + url.search);
  }
}

/** Open the Login or Register modal named by the server-rendered hint. */
export function openAuthModalFromHint(): void {
  const hint = document
    .getElementById("splashConfig")
    ?.getAttribute("data-auth-modal-hint");
  if (document.querySelector(".modal.show") !== null) return;
  // Bootstrap adds .show on the next frame, so also skip when a shell
  // initialiser has just asked for another modal.
  if (document.querySelector(OTHER_MODAL_PENDING_SELECTOR) !== null) return;

  if (hint === "login" && document.getElementById("LoginModal") !== null) {
    loginModalOpener();
  } else if (
    hint === "register" &&
    document.getElementById("RegisterModal") !== null
  ) {
    registerModalOpener();
  }
}
