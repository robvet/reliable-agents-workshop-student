from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ModelConfig:
    """
    Model-specific configuration for API calls.
    Each model must explicitly specify all parameters - no defaults.
    Supports unbounded key-value pairs via extra_params for model-specific parameters.
    """
    temperature: float
    max_tokens: Optional[int]  # None means don't include the parameter in API call
    stream: bool
    extra_params: Dict[str, Any] = field(default_factory=dict)  # Unbounded key-value pairs for model-specific params

