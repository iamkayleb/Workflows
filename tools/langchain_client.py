"""
Shared LangChain client construction helpers.

Standardizes provider selection (GitHub Models first, then OpenAI fallback),
timeouts, retries, and environment overrides.
"""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass

from tools.llm_provider import DEFAULT_MODEL, GITHUB_MODELS_BASE_URL

logger = logging.getLogger(__name__)

ENV_PROVIDER = "LANGCHAIN_PROVIDER"
ENV_MODEL = "LANGCHAIN_MODEL"
ENV_TIMEOUT = "LANGCHAIN_TIMEOUT"
ENV_MAX_RETRIES = "LANGCHAIN_MAX_RETRIES"

PROVIDER_OPENAI = "openai"
PROVIDER_GITHUB = "github-models"


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid %s value %r; using default %s", name, value, default)
        return default


DEFAULT_TIMEOUT = _env_int(ENV_TIMEOUT, 60)
DEFAULT_MAX_RETRIES = _env_int(ENV_MAX_RETRIES, 2)


@dataclass(frozen=True)
class ClientInfo:
    client: object
    provider: str
    model: str

    @property
    def provider_label(self) -> str:
        return f"{self.provider}/{self.model}"


def _normalize_provider(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"github", "github_models", "github-models"}:
        return PROVIDER_GITHUB
    if normalized in {"openai"}:
        return PROVIDER_OPENAI
    return None


def _resolve_provider(provider: str | None, *, force_openai: bool) -> tuple[str | None, bool]:
    if force_openai:
        return PROVIDER_OPENAI, True
    if provider:
        return _normalize_provider(provider), True
    env_provider = os.environ.get(ENV_PROVIDER)
    return _normalize_provider(env_provider), False


def _resolve_model(model: str | None) -> str:
    env_model = os.environ.get(ENV_MODEL)
    return model or env_model or DEFAULT_MODEL


def _build_openai_client(
    chat_openai: type, *, model: str, token: str, timeout: int, max_retries: int
) -> object:
    return chat_openai(
        model=model,
        api_key=token,
        temperature=0.1,
        timeout=timeout,
        max_retries=max_retries,
    )


def _build_github_client(
    chat_openai: type, *, model: str, token: str, timeout: int, max_retries: int
) -> object:
    return chat_openai(
        model=model,
        base_url=GITHUB_MODELS_BASE_URL,
        api_key=token,
        temperature=0.1,
        timeout=timeout,
        max_retries=max_retries,
    )


def build_chat_client(
    *,
    model: str | None = None,
    provider: str | None = None,
    force_openai: bool = False,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> ClientInfo | None:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    github_token = os.environ.get("GITHUB_TOKEN")
    openai_token = os.environ.get("OPENAI_API_KEY")
    if not github_token and not openai_token:
        return None

    selected_model = _resolve_model(model)
    selected_timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    selected_retries = DEFAULT_MAX_RETRIES if max_retries is None else max_retries

    selected_provider, provider_explicit = _resolve_provider(provider, force_openai=force_openai)
    if provider_explicit and selected_provider is None:
        return None

    if selected_provider == PROVIDER_GITHUB:
        if not github_token:
            return None
        try:
            client = _build_github_client(
                ChatOpenAI,
                model=selected_model,
                token=github_token,
                timeout=selected_timeout,
                max_retries=selected_retries,
            )
            return ClientInfo(client=client, provider=PROVIDER_GITHUB, model=selected_model)
        except Exception:
            return None

    if selected_provider == PROVIDER_OPENAI:
        if not openai_token:
            return None
        try:
            client = _build_openai_client(
                ChatOpenAI,
                model=selected_model,
                token=openai_token,
                timeout=selected_timeout,
                max_retries=selected_retries,
            )
            return ClientInfo(client=client, provider=PROVIDER_OPENAI, model=selected_model)
        except Exception:
            return None

    # Auto-select: GitHub Models first, OpenAI fallback.
    if github_token:
        with contextlib.suppress(Exception):
            # GitHub Models failed, try OpenAI fallback
            client = _build_github_client(
                ChatOpenAI,
                model=selected_model,
                token=github_token,
                timeout=selected_timeout,
                max_retries=selected_retries,
            )
            return ClientInfo(client=client, provider=PROVIDER_GITHUB, model=selected_model)

    if openai_token:
        try:
            client = _build_openai_client(
                ChatOpenAI,
                model=selected_model,
                token=openai_token,
                timeout=selected_timeout,
                max_retries=selected_retries,
            )
            return ClientInfo(client=client, provider=PROVIDER_OPENAI, model=selected_model)
        except Exception:
            return None

    return None


def build_chat_clients(
    *,
    model1: str | None = None,
    model2: str | None = None,
    provider: str | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> list[ClientInfo]:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return []

    github_token = os.environ.get("GITHUB_TOKEN")
    openai_token = os.environ.get("OPENAI_API_KEY")
    if not github_token and not openai_token:
        return []

    selected_timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    selected_retries = DEFAULT_MAX_RETRIES if max_retries is None else max_retries

    first_model = _resolve_model(model1)
    second_model = model2 or model1 or os.environ.get(ENV_MODEL) or DEFAULT_MODEL

    selected_provider, provider_explicit = _resolve_provider(provider, force_openai=False)
    if provider_explicit and selected_provider is None:
        return []

    clients: list[ClientInfo] = []

    if selected_provider:
        if selected_provider == PROVIDER_GITHUB and github_token:
            # GitHub Models client initialization failed - skip this provider
            with contextlib.suppress(Exception):
                clients.append(
                    ClientInfo(
                        client=_build_github_client(
                            ChatOpenAI,
                            model=first_model,
                            token=github_token,
                            timeout=selected_timeout,
                            max_retries=selected_retries,
                        ),
                        provider=PROVIDER_GITHUB,
                        model=first_model,
                    )
                )
            if second_model != first_model:
                # GitHub Models client initialization failed - skip this provider
                with contextlib.suppress(Exception):
                    clients.append(
                        ClientInfo(
                            client=_build_github_client(
                                ChatOpenAI,
                                model=second_model,
                                token=github_token,
                                timeout=selected_timeout,
                                max_retries=selected_retries,
                            ),
                            provider=PROVIDER_GITHUB,
                            model=second_model,
                        )
                    )
        if selected_provider == PROVIDER_OPENAI and openai_token:
            # OpenAI client initialization failed - skip this provider
            with contextlib.suppress(Exception):
                clients.append(
                    ClientInfo(
                        client=_build_openai_client(
                            ChatOpenAI,
                            model=first_model,
                            token=openai_token,
                            timeout=selected_timeout,
                            max_retries=selected_retries,
                        ),
                        provider=PROVIDER_OPENAI,
                        model=first_model,
                    )
                )
            if second_model != first_model:
                # OpenAI client initialization failed - skip this provider
                with contextlib.suppress(Exception):
                    clients.append(
                        ClientInfo(
                            client=_build_openai_client(
                                ChatOpenAI,
                                model=second_model,
                                token=openai_token,
                                timeout=selected_timeout,
                                max_retries=selected_retries,
                            ),
                            provider=PROVIDER_OPENAI,
                            model=second_model,
                        )
                    )
        return clients

    if github_token:
        # GitHub Models client initialization failed - skip this provider
        with contextlib.suppress(Exception):
            clients.append(
                ClientInfo(
                    client=_build_github_client(
                        ChatOpenAI,
                        model=first_model,
                        token=github_token,
                        timeout=selected_timeout,
                        max_retries=selected_retries,
                    ),
                    provider=PROVIDER_GITHUB,
                    model=first_model,
                )
            )

    if openai_token:
        # OpenAI client initialization failed - skip this provider
        with contextlib.suppress(Exception):
            clients.append(
                ClientInfo(
                    client=_build_openai_client(
                        ChatOpenAI,
                        model=second_model,
                        token=openai_token,
                        timeout=selected_timeout,
                        max_retries=selected_retries,
                    ),
                    provider=PROVIDER_OPENAI,
                    model=second_model,
                )
            )

    return clients
