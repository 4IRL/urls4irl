from backend.utils.strings.json_strs import FAILURE_GENERAL

# Server-side messages for the share short-link API (mint / revoke). The
# SHORT_LINK_SUCCESS / SHORT_LINK_FAILURE classes are server messages only. The
# SHORT_LINK_UI class holds the URL-card copy that TypeScript renders; it is bridged
# to APP_CONFIG.strings with a SHORT_LINK_ key prefix (see STRINGS /
# generate_strings_js()).

# Strings for short-link success
SHORT_LINK_CREATED = "Short link created."
SHORT_LINK_REUSED = "Short link already active."
SHORT_LINK_REVOKED = "Short link revoked."


class SHORT_LINK_SUCCESS:
    SHORT_LINK_CREATED = SHORT_LINK_CREATED
    SHORT_LINK_REUSED = SHORT_LINK_REUSED
    SHORT_LINK_REVOKED = SHORT_LINK_REVOKED


# Strings for short-link failure
UNABLE_TO_REVOKE = "Only the UTub owner, a co-owner, the person who added this URL or the person who made this link can revoke it."
SHORT_LINK_NOT_FOUND_MESSAGE = "This short link is no longer active."


class SHORT_LINK_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_REVOKE = UNABLE_TO_REVOKE
    SHORT_LINK_NOT_FOUND = SHORT_LINK_NOT_FOUND_MESSAGE


# URL-card short-link copy, read by TypeScript through APP_CONFIG.strings.SHORT_LINK_<NAME>
class SHORT_LINK_UI:
    TOOLTIP = "Copy short link"
    TOOLTIP_ACTIVE = "Copy short link (expires {date})"
    LINK_REMOVED_SUFFIX = "Its short link was removed."
    COPIED = "Short link copied. Expires {date}."
    EXPIRES = "Short link active · expires {date}"
    REVOKE_LABEL = "Revoke"
    REVOKE_ARIA = "Revoke short link"
    REVOKED = SHORT_LINK_REVOKED
    CLIPBOARD_FALLBACK = "Couldn't copy automatically. Copy the link below."
    COPY_FAILED = "Couldn't create a short link. Try again."
    REVOKE_FAILED = "Couldn't revoke the short link. Try again."
    REVOKE_CONFIRM_TITLE = "Revoke short link?"
    REVOKE_CONFIRM_BODY = "Anyone who has this link will no longer be able to open it. It would otherwise expire on {date}."
