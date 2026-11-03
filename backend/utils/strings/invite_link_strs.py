from backend.utils.strings.json_strs import FAILURE_GENERAL

# Server-side messages for the invite link manager API (create / update / replace /
# revoke). Server messages only: nothing here is bridged to TypeScript.

# Strings for invite link success
INVITE_LINK_CREATED = "Invite link created."
INVITE_LINK_UPDATED = "Invite link updated."
INVITE_LINK_REPLACED = "Invite link replaced."
INVITE_LINK_REVOKED = "Invite link revoked."


class INVITE_LINK_SUCCESS:
    INVITE_LINK_CREATED = INVITE_LINK_CREATED
    INVITE_LINK_UPDATED = INVITE_LINK_UPDATED
    INVITE_LINK_REPLACED = INVITE_LINK_REPLACED
    INVITE_LINK_REVOKED = INVITE_LINK_REVOKED


# Strings for invite link failure
INVITE_LINK_NOT_FOUND_MESSAGE = "This UTub has no active invite link."
INVALID_INVITE_LINK_INPUT = "Unable to process the invite link settings."
UTUB_IS_LOCKED_MESSAGE = "Invite links can't be changed while this UTub is locked."
LIVE_LINK_EXISTS_MESSAGE = "This UTub already has a live invite link."
DEAD_LINK_UPDATE_MESSAGE = (
    "This invite link has expired or can no longer be used. Replace it instead."
)
USES_BELOW_JOINED_MESSAGE = (
    "The use limit can't be lower than the number of people who already joined."
)


class INVITE_LINK_FAILURE(FAILURE_GENERAL):
    INVITE_LINK_NOT_FOUND = INVITE_LINK_NOT_FOUND_MESSAGE
    INVALID_FORM_INPUT = INVALID_INVITE_LINK_INPUT
    UTUB_IS_LOCKED = UTUB_IS_LOCKED_MESSAGE
    LIVE_LINK_EXISTS = LIVE_LINK_EXISTS_MESSAGE
    DEAD_LINK_UPDATE = DEAD_LINK_UPDATE_MESSAGE
    USES_BELOW_JOINED = USES_BELOW_JOINED_MESSAGE
