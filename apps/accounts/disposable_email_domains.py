"""
Hardcoded blocklist of disposable / throwaway email domains.

Extend this list as new services are discovered. Domains are lowercase.
Sources: public community lists (disposable-email-domains, block-disposable-email).
"""

DISPOSABLE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    [
        # --- mailinator family ---
        "mailinator.com",
        "trashmail.com",
        "trashmail.at",
        "trashmail.me",
        "trashmail.io",
        "trashmail.xyz",
        "trashmail.net",
        "trashmail.org",
        # --- guerrillamail family ---
        "guerrillamail.com",
        "guerrillamail.net",
        "guerrillamail.org",
        "guerrillamail.biz",
        "guerrillamail.de",
        "guerrillamail.info",
        "sharklasers.com",
        "guerrillamailblock.com",
        "grr.la",
        "spam4.me",
        # --- yopmail family ---
        "yopmail.com",
        "yopmail.fr",
        "yopmail.net",
        "cool.fr.nf",
        "jetable.fr.nf",
        "nospam.ze.tc",
        "nomail.xl.cx",
        "mega.zik.dj",
        "speed.1s.fr",
        "courriel.fr.nf",
        "moncourrier.fr.nf",
        "monemail.fr.nf",
        "monmail.fr.nf",
        # --- 10-minute-mail family ---
        "10minutemail.com",
        "10minutemail.net",
        "10minutemail.org",
        "10minutemail.de",
        "10minutemail.nl",
        # --- temp-mail family ---
        "tempmail.com",
        "temp-mail.org",
        "temp-mail.io",
        "tempr.email",
        "tempail.com",
        "mytemp.email",
        "mailtemp.net",
        # --- discard / throwaway ---
        "fakeinbox.com",
        "mailnull.com",
        "spamgourmet.com",
        "spamgourmet.org",
        "spamgourmet.net",
        "dispostable.com",
        "throwam.com",
        "throwam.net",
        "throwaway.email",
        "discard.email",
        "mailnesia.com",
        # --- burner / getnada / maildrop ---
        "getnada.com",
        "maildrop.cc",
        "mailsac.com",
        "emailondeck.com",
        "fakemailgenerator.com",
        # --- wegwerf (German disposable) ---
        "wegwerfmail.de",
        "wegwerfmail.net",
        "wegwerfmail.org",
        # --- jetable family ---
        "jetable.com",
        "jetable.net",
        "jetable.org",
        # --- misc ---
        "nwytg.net",
        "crazymailing.com",
        "moakt.com",
        "mohmal.com",
        "inboxbear.com",
        "anonbox.net",
        "spamdecoy.net",
        "spamgenie.com",
        "spamevader.com",
        "spaml.de",
        "sofimail.com",
        "tempinbox.com",
        "mailexpire.com",
    ]
)
