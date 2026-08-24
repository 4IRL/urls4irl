import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { setState } from "../../store/app-store.js";

import type { SuccessResponse } from "../../types/api-helpers.d.ts";

type CoMemberCandidatesResponse = SuccessResponse<"getCoMemberCandidatesRoute">;

// The in-flight candidate request, if any. Each open/UTub-switch/quick-reopen
// aborts its predecessor before firing (abort-and-replace), so a stale prior
// fetch can never resolve into the store after a newer one has been issued.
// Because loadCoMemberCandidates is the only fetch in the co-member data path,
// this single guard covers every caller — no sibling fetch chokepoint exists.
let _inFlight: JQuery.jqXHR | null = null;

/**
 * Hydrates the co-member add candidates for the target UTub once, when the add
 * UI opens. On success the candidate list + loaded flag are written to the
 * store; on failure the slice degrades to an empty list (the combobox still
 * offers the outsider fallback, and the "Loading matches…" hint clears even on
 * failure) with the loaded flag still flipped true so "loaded and empty" is
 * distinguishable from "not yet loaded". Follows the GET conventions of
 * cross-utub-search.ts (no CSRF needed for GET).
 */
export function loadCoMemberCandidates(utubID: number): void {
  _inFlight?.abort();
  _inFlight = ajaxCall(
    "GET",
    APP_CONFIG.routes.coMemberCandidates(utubID),
    null,
  )
    .done((data: CoMemberCandidatesResponse) => {
      setState({
        coMemberCandidates: data.members ?? [],
        coMemberCandidatesLoaded: true,
      });
    })
    .fail((xhr: JQuery.jqXHR) => {
      if (is429Handled(xhr)) return;
      // An aborted jqXHR (abort-and-replace above, or an ancestor 302 the
      // browser follows) surfaces as status 0; a newer fetch owns the store,
      // so this stale one must not degrade it to empty.
      if (xhr.status === 0) return;
      setState({ coMemberCandidates: [], coMemberCandidatesLoaded: true });
    })
    .always(() => {
      _inFlight = null;
    });
}

/**
 * Aborts any in-flight candidate fetch without degrading the store. Called from
 * teardown paths (e.g. resetMemberDeck on a UTub switch that does NOT reopen the
 * add UI, so loadCoMemberCandidates is not re-issued to supersede it) so a
 * response from the prior UTub can never resolve into the store after the slice
 * has been cleared. Mirrors exitCrossUtubSearchMode's teardown abort
 * (cross-utub-search.ts:484). The aborted jqXHR surfaces as status 0, which the
 * .fail handler above already ignores, so this never degrades the slice.
 */
export function cancelCoMemberCandidatesFetch(): void {
  _inFlight?.abort();
  _inFlight = null;
}
