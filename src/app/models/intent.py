from enum import Enum

class Intent(str, Enum):
    # Map to concrete user intents recognized by the system
    EVENT_RESPONSE = "EVENT_RESPONSE"
    SITUATIONAL_AWARENESS = "SITUATIONAL_AWARENESS"
    RELIABILITY = "RELIABILITY"
    MAJOR_EVENT = "MAJOR_EVENT"
    CUSTOMER_STATUS = "CUSTOMER_STATUS"
    CROSS_DOMAIN = "CROSS_DOMAIN"
    # Map open-ended read-only lookup rqeuests to a dedicated query agent
    DOMAIN_LOOKUP = "DOMAIN_LOOKUP"
    # Map questions that fall outside of the application domain to UNKNOWN.
    UNKNOWN = "UNKNOWN"
    # Map system-level error states
    ERROR = "ERROR"

    # Architectural Insight
    # Keep ERROR and UNKNOWN distinct.
    # Keeping each distinct as an outage must never
    # masquerade as a benign UNKNOWN fallback.
    # ERROR is a SYSTEM control state, a technical fault
    # ONLY deterministic code may set ERROR, The model cannot emit it
    # The intent prompt forbids it, and IntentResult's validator
    # coerces any bare ERROR back to UNKNOWN as a backstop.
   
