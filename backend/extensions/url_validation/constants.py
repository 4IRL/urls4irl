PROTOCOL = "protocol"
HOSTNAME = "hostname"
HREF = "href"

INVALID_SCHEME_PREFIXES = (
    "javascript",
    "data",
    "vbscript",
    "moz",
    "about",
    "resource",
    "jar",
    "chrome",
    "edge",
    "view-source",
    "safari",
    "webkit",
    "ms-browser",
    "file",  # Do not leak local file paths of users to other, consider only for private UTubs
)

CORE_SCHEMES = {
    "https",
    "http",
    "mailto",
    "ftp",
    "ftps",
    "tel",
    "sms",
    "ws",
    "wss",
    "feed",
    "urn",
    "magnet",
    "webcal",
    "geo",
}

OTHER_VALID_SCHEMES = {
    # Might be considered for private UTubs only
    "ssh",
    "sftp",
    "git",
    "irc",
    "ircs",
    "xmpp",
    "sip",
    "sips",
    "rtsp",
    "ldap",
    "mms",
    # App schemes
    "zoom",
    "slack",
    "discord",
    "spotify",
    "steam",
    "vscode",
    "obsidian",
    "notion",
    "figma",
    "miro",
    "itms",
    "itms-apps",
    "market",
    "intent",
    "youtube",
    "netflix",
    "twitch",
    # Niche
    "ipfs",
    "ipns",
    "news",
    "nntp",
    "gopher",
    "gemini",
}

DEFAULT_URL_SCHEME = "https"

PINNED_URL_SCHEMES = ("https", "http")

# Schemes whose canonical form is `scheme://`. Every other whitelisted scheme is
# opaque (`scheme:` followed by whatever the user typed), so new whitelist entries
# default to the safe, lossless opaque handling.
AUTHORITY_URL_SCHEMES: frozenset[str] = frozenset(
    {
        "https",
        "http",
        "ftp",
        "ftps",
        "ws",
        "wss",
        "webcal",
        "sftp",
        "ssh",
        "git",
        "irc",
        "ircs",
        "rtsp",
        "ldap",
        "mms",
        "zoom",
        "slack",
        "discord",
        "steam",
        "vscode",
        "obsidian",
        "notion",
        "figma",
        "miro",
        "itms",
        "itms-apps",
        "market",
        "intent",
        "youtube",
        "netflix",
        "twitch",
        "ipfs",
        "ipns",
        "nntp",
        "gopher",
        "gemini",
    }
)


def ordered_url_schemes() -> list[str]:
    """The whitelist in display order: pinned first, then core, then other (each alphabetical)."""
    return [
        *PINNED_URL_SCHEMES,
        *sorted(CORE_SCHEMES - set(PINNED_URL_SCHEMES)),
        *sorted(OTHER_VALID_SCHEMES),
    ]


DEV_URLS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
)

TRACKING_QUERY_PARAMS: frozenset[str] = frozenset(
    {
        "gclid",
        "gclsrc",
        "dclid",
        "gbraid",
        "wbraid",
        "gad_source",
        "gad_campaignid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "_hsenc",
        "_hsmi",
        "__hssc",
        "__hstc",
        "__hsfp",
        "hsctatracking",
        "igshid",
        "ttclid",
        "twclid",
        "yclid",
        "mkt_tok",
        "s_kwcid",
        "vero_id",
        "oly_anon_id",
        "oly_enc_id",
        "wickedid",
    }
)

TRACKING_QUERY_PARAM_PREFIXES: tuple[str, ...] = ("utm_",)

WEB_SCHEMES_FOR_TRACKING_STRIP: frozenset[str] = frozenset({"http", "https"})
