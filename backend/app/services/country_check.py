DISCLAIMER = "Informational only — not legal advice. Consult a local legal professional."

COUNTRY_RULES = {
    "DE": {
        "collective_consent_sufficient": None,
        "summary_en": (
            "Recording non-public spoken words generally requires the consent of all speakers "
            "and is otherwise a criminal offense under § 201 StGB. Consent of the parties may "
            "resolve civil liability but cannot override criminal liability. Verify with a local "
            "legal professional before capturing audio."
        ),
        "summary_de": (
            "Das Aufnehmen nicht öffentlich gesprochener Worte erfordert grundsätzlich die "
            "Einwilligung aller Sprecher und ist andernfalls nach § 201 StGB strafbar. Eine "
            "Einwilligung der Parteien kann die zivilrechtliche Haftung entfallen lassen, hebt "
            "die strafrechtliche Verantwortung jedoch nicht auf. Vor Audioaufnahmen einen "
            "Rechtsanwalt vor Ort konsultieren."
        ),
        "source": "§ 201 StGB (Germany)",
        "confidence": "medium",
    },
    "AT": {
        "collective_consent_sufficient": None,
        "summary_en": (
            "Recording non-public spoken words is restricted under § 120 StGB. Rules on "
            "collective consent and criminal liability are not verified here. Verify with a "
            "local legal professional before capturing audio."
        ),
        "summary_de": (
            "Das Aufnehmen nicht öffentlich gesprochener Worte ist nach § 120 StGB beschränkt. "
            "Die Regeln zu gemeinsamer Einwilligung und strafrechtlicher Haftung sind hier nicht "
            "verifiziert. Vor Audioaufnahmen einen Rechtsanwalt vor Ort konsultieren."
        ),
        "source": "§ 120 StGB (Austria)",
        "confidence": "low",
    },
    "CH": {
        "collective_consent_sufficient": None,
        "summary_en": (
            "Recording third-party conversations is restricted under Art. 179bis StGB. Rules on "
            "collective consent and criminal liability are not verified here. Verify with a "
            "local legal professional before capturing audio."
        ),
        "summary_de": (
            "Das Aufnehmen fremder Gespräche ist nach Art. 179bis StGB beschränkt. Die Regeln zu "
            "gemeinsamer Einwilligung und strafrechtlicher Haftung sind hier nicht verifiziert. "
            "Vor Audioaufnahmen einen Rechtsanwalt vor Ort konsultieren."
        ),
        "source": "Art. 179bis StGB (Switzerland)",
        "confidence": "low",
    },
    "US": {
        "collective_consent_sufficient": None,
        "summary_en": (
            "Recording consent rules vary by state: many states allow one-party consent, others "
            "require all-party consent. Not verified here. Verify with a local legal professional "
            "before capturing audio."
        ),
        "summary_de": (
            "Die Aufnahmeregeln variieren je nach Bundesstaat: viele Staaten erlauben die "
            "Einwilligung einer Partei, andere verlangen die Einwilligung aller Parteien. Hier "
            "nicht verifiziert. Vor Audioaufnahmen einen Rechtsanwalt vor Ort konsultieren."
        ),
        "source": "Varies by state (one-party vs all-party consent)",
        "confidence": "low",
    },
    "UK": {
        "collective_consent_sufficient": None,
        "summary_en": (
            "Recording rules depend on context (common law and the Regulation of Investigatory "
            "Powers Act 2000). Not verified here. Verify with a local legal professional before "
            "capturing audio."
        ),
        "summary_de": (
            "Die Aufnahmeregeln hängen vom Kontext ab (Common Law und Regulation of "
            "Investigatory Powers Act 2000). Hier nicht verifiziert. Vor Audioaufnahmen einen "
            "Rechtsanwalt vor Ort konsultieren."
        ),
        "source": "Common law + Regulation of Investigatory Powers Act 2000",
        "confidence": "low",
    },
    "unknown": {
        "collective_consent_sufficient": None,
        "summary_en": (
            "Recording rules could not be verified for this country. Consult a local legal "
            "professional before using audio capture in this country."
        ),
        "summary_de": (
            "Die Aufnahmeregeln konnten für dieses Land nicht verifiziert werden. Vor "
            "Audioaufnahmen in diesem Land einen Rechtsanwalt vor Ort konsultieren."
        ),
        "source": "unverified",
        "confidence": "low",
    },
}


def get_country(code: str) -> dict:
    key = code.strip().upper()
    return COUNTRY_RULES.get(key, COUNTRY_RULES["unknown"])
