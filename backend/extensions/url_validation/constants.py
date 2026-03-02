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

DEV_URLS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
)
