"""
AzureIdentityProvider — centralized Azure Entra (Azure AD) authentication.

Single responsibility: encapsulate DefaultAzureCredential and token provider creation
for Azure OpenAI agents. Transport concerns (HTTP clients, timeouts) stay with the agents.

Architecture role:
- Think of this like a C# static singleton — one shared instance across all consumers.
- Equivalent to registering a single ITokenCredentialFactory in a DI container.
- Agents call AzureIdentityProvider.default() to get the shared instance, then use
  identity.token_provider to authenticate their Azure OpenAI clients.

Why a singleton?
- DefaultAzureCredential builds an internal chain of credential providers.
  Creating multiple chains is wasteful — they all resolve the same way.
- The token provider returned by get_bearer_token_provider already handles
  caching and automatic refresh internally. One instance is sufficient.
"""

from azure.identity import DefaultAzureCredential, get_bearer_token_provider


class AzureIdentityProvider:
    """
    Provides Azure Entra (Azure AD) authentication for Azure OpenAI agents.

    This class builds a credential chain and wraps it in a token provider.
    Multiple agents (GPT, Grok, DeepSeek) share one instance via the
    default() class method — similar to a C# static singleton.

    IMPORTANT: The constructor BUILDS the credential chain but does NOT
    EXECUTE it. No network calls happen here. The chain is lazy — actual
    token acquisition occurs on first API call through the token provider.
    """

    # Singleton instance — shared across all consumers.
    # Similar to C#: private static AzureIdentityProvider _instance;
    _instance = None

    def __init__(self, scope: str = "https://cognitiveservices.azure.com/.default") -> None:
        """
        Initialize the identity provider by BUILDING (not executing) a credential chain.

        Args:
            scope: The OAuth scope for token acquisition.
                   Defaults to Azure Cognitive Services scope, which covers Azure OpenAI.

        How the credential chain works:
        - DefaultAzureCredential is a TOKEN CREDENTIAL CHAIN (not a token itself).
        - Think of it like a C# Chain of Responsibility pattern — it tries each
          credential provider in order until one succeeds.
        - CRITICALLY: this constructor only ASSEMBLES the chain. No authentication
          happens here. The chain executes lazily on the first call to get a token.

        The chain tries these providers in order:
        1. EnvironmentCredential      — service principal via env vars (CI/CD pipelines)
        2. WorkloadIdentityCredential  — federated identity (Kubernetes, GitHub Actions)
        3. ManagedIdentityCredential   — Azure-assigned host identity (App Service, VMs)
        4. SharedTokenCacheCredential  — cached token from a previous user sign-in
        5. AzureCliCredential          — az login session (local development)
        6. AzurePowerShellCredential   — Connect-AzAccount session
        7. AzureDeveloperCliCredential — azd auth login session

        For local development, #5 (az login) is typically what resolves.
        In production on Azure, #3 (Managed Identity) is the recommended approach.
        """
        # BUILD the credential chain — no network call, no token request.
        # This is equivalent to: var credential = new DefaultAzureCredential();
        self._credential = DefaultAzureCredential()

        # Wrap the credential in an SDK-managed token provider.
        # This provider handles token caching and automatic refresh internally.
        # Again, no network call here — the provider is a callable that will
        # fetch/refresh tokens lazily when invoked by the Azure OpenAI client.
        self._token_provider = get_bearer_token_provider(self._credential, scope)


    ####### Python Convention #################
    # Python convention for a static singleton accessor — similar to C#'s public static Instance property.  
    # The caller invokes method with no parameter: identity = AzureIdentityProvider.default()
    # But, Python automagically injects cls parameter, which refers to the class itself (AzureIdentityProvider).
    # So, it reads as: identity = AzureIdentityProvider.default(AzureIdentityProvider)
    ###########################################
    @classmethod
    def default(cls):
        """
        Return the shared singleton instance of AzureIdentityProvider.

        Equivalent to C#: public static AzureIdentityProvider Instance { get; }

        First call creates the instance. All subsequent calls return the same one.
        This means all agents share one credential chain and one token provider,
        avoiding redundant object creation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def token_provider(self):
        """
        Return the SDK-managed token provider for Azure OpenAI clients.

        This is a callable that the Azure OpenAI SDK invokes automatically
        whenever it needs a bearer token. The SDK handles when to call it —
        agents just pass it during client construction and never touch it again.
        """
        return self._token_provider
