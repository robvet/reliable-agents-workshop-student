from enum import Enum


class Intent(str, Enum):
    EVENT_RESPONSE = "EVENT_RESPONSE"
    SITUATIONAL_AWARENESS = "SITUATIONAL_AWARENESS"
    RELIABILITY = "RELIABILITY"
    MAJOR_EVENT = "MAJOR_EVENT"
    CUSTOMER_STATUS = "CUSTOMER_STATUS"
    CROSS_DOMAIN = "CROSS_DOMAIN"
    # Open-ended read-only lookup against Reliable Agents' own domains ("list the assets
    # in the south region"). These questions go directly to the dedicated query agent.
    # Off-domain questions fall to UNKNOWN.
    DOMAIN_LOOKUP = "DOMAIN_LOOKUP"
    UNKNOWN = "UNKNOWN"
    # *********************************************
    # *********  Architectural Insights *************
    # *********************************************
    # ERROR is a SYSTEM control state, not a user intent. It means "the intent
    # hop itself failed" (model call threw, or returned no valid structure) - a
    # technical fault, NOT "the user asked something we can't classify" (that is
    # UNKNOWN). Keeping the two distinct is the whole point: an outage must never
    # masquerade as a benign UNKNOWN fallback.
    #
    # Critical rule: ONLY deterministic code may set ERROR. The model must never
    # emit it - the intent prompt forbids it, and IntentResult's validator
    # coerces any bare ERROR back to UNKNOWN as a backstop.
    ERROR = "ERROR"
