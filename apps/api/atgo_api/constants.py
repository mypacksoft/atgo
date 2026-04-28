"""Reserved subdomains, blocklists, and other constants."""

RESERVED_SUBDOMAINS: frozenset[str] = frozenset({
    # Infra / system
    "www", "app", "api", "admin", "adms", "cname", "mail", "smtp", "imap",
    "pop", "ns", "ns1", "ns2", "mx", "dmarc", "dkim", "spf", "edge", "cdn",
    "static", "assets", "media", "internal", "vpn", "ssh", "ws", "websocket",
    # Path-based mode collisions (when atgo.io/<slug> is used as a workspace,
    # these path segments must NOT be claimable as slugs):
    "iclock",       # ZKTeco ADMS endpoint /iclock/cdata
    "_admin",       # internal admin
    "_next",        # Next.js static
    "_internal",    # internal API
    "favicon.ico", "robots.txt", "sitemap.xml", "manifest.webmanifest",
    "manifest.json", "icon-192.png", "apple-touch-icon.png",
    # Product
    "me", "billing", "support", "help", "docs", "status",
    "odoo", "portal", "employee", "employees", "dashboard",
    # Auth
    "login", "logout", "auth", "oauth", "signin", "signup", "register",
    # Legal / marketing
    "pricing", "terms", "privacy", "legal", "careers", "jobs", "blog",
    "about", "contact", "press",
    # Generic
    "demo", "test", "staging", "dev", "prod", "root", "system", "security",
    "ssl", "verify", "webhook", "verification",
})

# Domains that ATGO itself uses — never let a tenant claim these
SYSTEM_DOMAIN_BLOCKLIST: frozenset[str] = frozenset({
    "atgo.io",
    "atgo.com",
    "atgo.app",
    "api.atgo.io",
    "admin.atgo.io",
    "adms.atgo.io",
    "cname.atgo.io",
    "app.atgo.io",
    "status.atgo.io",
    "docs.atgo.io",
    "blog.atgo.io",
    "www.atgo.io",
})

# Public-suffix-ish guard against people typing just 'com' / 'co.uk'
PUBLIC_SUFFIX_REJECT: frozenset[str] = frozenset({
    "com", "net", "org", "io", "co", "co.uk", "uk", "vn", "com.vn",
    "us", "de", "fr", "it", "es", "jp", "cn", "in", "co.in",
})

# ZKTeco punch_state values (industry standard)
PUNCH_STATE_CHECK_IN = 0
PUNCH_STATE_CHECK_OUT = 1
PUNCH_STATE_BREAK_OUT = 2
PUNCH_STATE_BREAK_IN = 3
PUNCH_STATE_OVERTIME_IN = 4
PUNCH_STATE_OVERTIME_OUT = 5

PUNCH_STATE_LABEL: dict[int, str] = {
    0: "check_in",
    1: "check_out",
    2: "break_out",
    3: "break_in",
    4: "overtime_in",
    5: "overtime_out",
}

# Pricing matrix — geo-aware. Amounts are in MINOR units of the local currency
# (e.g. cents for USD, dong for VND, paise for INR).
PRICING_MATRIX: dict[str, dict] = {
    "VN": {
        "currency": "VND",
        "providers": ["vnpay", "momo", "paddle"],
        "default_provider": "vnpay",
        "tax_inclusive": True,
        "plans": {
            "starter":  199_000,
            "business": 590_000,
            "scale":    990_000,
            "hr_pro":   1_590_000,
        },
    },
    "IN": {
        "currency": "INR",
        "providers": ["razorpay", "paddle"],
        "default_provider": "razorpay",
        "tax_inclusive": False,
        "plans": {
            "starter":  39900,    # ₹399
            "business": 129900,   # ₹1299
            "scale":    219900,
            "hr_pro":   349900,
        },
    },
    "DEFAULT": {
        "currency": "USD",
        "providers": ["paddle"],
        "default_provider": "paddle",
        "tax_inclusive": False,
        "plans": {
            "starter":  900,    # $9.00
            "business": 2900,
            "scale":    4900,
            "hr_pro":   7900,
        },
    },
}
