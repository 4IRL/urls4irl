# Strings for the cross-UTub search frontend UI.
# These are read dynamically by TypeScript via APP_CONFIG.strings, so they go
# through the full APP_CONFIG bridge (constants.STRINGS + generate_strings_js()
# + frontend/test-setup.ts mock). Individual-constant pattern, matching
# url_strs.py / utub_strs.py.

CROSS_SEARCH_NO_RESULTS = "No results found across your UTubs"
CROSS_SEARCH_SHORT_QUERY = "Type a search and press Enter or the search button"
CROSS_SEARCH_PLACEHOLDER = "Search all your UTubs"
CROSS_SEARCH_COUNT_TEMPLATE = "{{ count }} results across {{ utubs }} UTubs"

# Navbar trigger + submit/refresh button labels. Read dynamically by TypeScript
# (the trigger morphs open<->close and the submit button morphs search<->refresh),
# so they go through the full APP_CONFIG bridge.
CROSS_SEARCH_TRIGGER_OPEN_LABEL = "Search across your UTubs"
CROSS_SEARCH_TRIGGER_CLOSE_LABEL = "Close search"
CROSS_SEARCH_SUBMIT_LABEL = "Search across your UTubs"
CROSS_SEARCH_REFRESH_LABEL = "Refresh these search results"

# Field display names for the three MatchedField values.
CROSS_SEARCH_FIELD_URL = "URL"
CROSS_SEARCH_FIELD_TITLE = "Title"
CROSS_SEARCH_FIELD_TAG = "Tag"

# Recent-search history strings.
CROSS_SEARCH_HISTORY_HEADING = "Recent searches"
CROSS_SEARCH_HISTORY_CLEAR = "Clear"
