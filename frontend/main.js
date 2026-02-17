import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import {
  registerJQueryPlugins,
  enableTabbableChildElements,
  disableTabbableChildElements,
} from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { ajaxCall, debugCall } from "./lib/ajax.js";
import { showNewPageOnAJAXHTMLResponse } from "./lib/page-utils.js";
import {
  KEYS,
  METHOD_TYPES,
  INPUT_TYPES,
  SHOW_LOADING_ICON_AFTER_MS,
  TABLET_WIDTH,
} from "./lib/constants.js";

import * as btnsForms from "./home/btns-forms.js";
import * as visibility from "./home/visibility.js";
import * as homeInit from "./home/init.js";
import * as navbar from "./home/navbar.js";
import * as mobile from "./home/mobile.js";
import * as windowEvents from "./home/window-events.js";
import * as collapsibleDecks from "./home/collapsible-decks.js";
import * as utubsDeck from "./home/utubs/deck.js";
import * as utubsUtils from "./home/utubs/utils.js";
import * as utubsSelectors from "./home/utubs/selectors.js";
import * as utubsSearch from "./home/utubs/search.js";
import * as utubsCreate from "./home/utubs/create.js";
import * as utubsDelete from "./home/utubs/delete.js";
import * as utubsStaleData from "./home/utubs/stale-data.js";
import * as membersDeck from "./home/members/deck.js";
import * as members from "./home/members/members.js";
import * as membersCreate from "./home/members/create.js";
import * as membersDelete from "./home/members/delete.js";
import * as tagsDeck from "./home/tags/deck.js";
import * as tags from "./home/tags/tags.js";
import * as tagsUtils from "./home/tags/utils.js";
import * as tagsCreate from "./home/tags/create.js";
import * as tagsDelete from "./home/tags/delete.js";
import * as tagsUnselectAll from "./home/tags/unselect-all.js";
import * as tagsUpdateAll from "./home/tags/update-all.js";
import * as urlsDeck from "./home/urls/deck.js";
import * as urlsUtils from "./home/urls/utils.js";
import * as urlsValidation from "./home/urls/validation.js";
import * as urlsCreateBtns from "./home/urls/create-btns.js";
import * as urlsAccessAll from "./home/urls/access-all.js";
import * as urlsUpdateName from "./home/urls/update-name.js";
import * as urlsUpdateDescription from "./home/urls/update-description.js";
import * as urlCards from "./home/urls/cards/cards.js";
import * as urlCardsCreate from "./home/urls/cards/create.js";
import * as urlCardsDelete from "./home/urls/cards/delete.js";
import * as urlCardsGet from "./home/urls/cards/get.js";
import * as urlCardsUpdateString from "./home/urls/cards/update-string.js";
import * as urlCardsUpdateTitle from "./home/urls/cards/update-title.js";
import * as urlCardsCopy from "./home/urls/cards/copy.js";
import * as urlCardsAccess from "./home/urls/cards/access.js";
import * as urlCardsCornerAccess from "./home/urls/cards/corner-access.js";
import * as urlCardsFiltering from "./home/urls/cards/filtering.js";
import * as urlCardsLoading from "./home/urls/cards/loading.js";
import * as urlCardsSelection from "./home/urls/cards/selection.js";
import * as urlCardsUrlString from "./home/urls/cards/url-string.js";
import * as urlCardsUrlTitle from "./home/urls/cards/url-title.js";
import * as urlCardsUtils from "./home/urls/cards/utils.js";
import * as urlCardsOptionsBtns from "./home/urls/cards/options/btns.js";
import * as urlCardsOptionsAccessBtn from "./home/urls/cards/options/access-btn.js";
import * as urlCardsOptionsCopyBtn from "./home/urls/cards/options/copy-btn.js";
import * as urlCardsOptionsEditStringBtn from "./home/urls/cards/options/edit-string-btn.js";
import * as urlCardsOptionsDeleteBtn from "./home/urls/cards/options/delete-btn.js";
import * as urlCardsOptionsTagBtn from "./home/urls/cards/options/tag-btn.js";
import * as urlTags from "./home/urls/tags/tags.js";
import * as urlTagsCreate from "./home/urls/tags/create.js";
import * as urlTagsDelete from "./home/urls/tags/delete.js";

// Register jQuery plugins and setup CSRF before DOM ready
registerJQueryPlugins();
setupCSRF();

// Initialize on DOM ready
$(document).ready(() => {
  btnsForms.initBtnsForms();
  visibility.initVisibilityHandlers();
  navbar.initNavbar();
  mobile.initMobileLayout();
  collapsibleDecks.initCollapsibleDecks();
  utubsCreate.setCreateUTubEventListeners();
  utubsDeck.setUTubEventListenersOnInitialPageLoad();
  tagsUnselectAll.initUnselectAllTags();
  tagsUpdateAll.initUpdateAllTags();
  urlsDeck.initURLDeck();
  urlsAccessAll.initAccessAllURLsBtn();
  initCookieBanner();
});

// Initialize window events (must be outside DOM ready)
windowEvents.initWindowEvents();
