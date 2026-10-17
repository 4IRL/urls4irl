import type { OutcomeBannerMount } from "../urls/outcome-banner.js";

/** The single mount every Trash module passes to show/clearOutcomeBanner. */
export const TRASH_BANNER_MOUNT: OutcomeBannerMount = {
  bannerSelector: "#TrashOutcomeBanner",
  rootSelector: "#TrashPanel",
};
