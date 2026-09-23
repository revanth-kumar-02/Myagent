"""
models.failover — Provider Failover & Health Manager

Responsibilities:
  - Track health of HuggingFace (Online) and Ollama (Local/Offline) providers
  - Detect online/offline network transitions and inference failures
  - Manage failover: HuggingFace -> Ollama on network loss, timeout, HTTP failure
  - Manage recovery: Ollama -> HuggingFace via periodic background health checks
  - Maintain provider state: ONLINE, OFFLINE, ONLINE_DEGRADED, LOCAL_FALLBACK, NO_PROVIDER
  - Broadcast PROVIDER_STATUS updates via callbacks for WebSocket push
  - Prevent duplicate responses and preserve clean streaming handoffs
"""

from __future__ import annotations

import asyncio
import enum
import time
from typing import Any, Awaitable, Callable

import httpx
import structlog

from config import settings
from models.providers.huggingface import HuggingFaceProvider
from models.providers.ollama import OllamaProvider

logger = structlog.get_logger(__name__)


class ProviderMode(str, enum.Enum):
    ONLINE = "online"
    ONLINE_CLOUD = "online"
    OFFLINE = "offline"
    OFFLINE_LOCAL = "offline"
    CONNECTING = "connecting"
    DEGRADED = "online_degraded"
    ONLINE_DEGRADED = "online_degraded"
    LOCAL_FALLBACK = "local_fallback"
    NO_PROVIDER = "no_provider"


class ProviderFailoverManager:
    """
    Manages online/offline detection, active provider routing, and automatic recovery.
    """

    def __init__(
        self,
        hf_provider: HuggingFaceProvider | None = None,
        ollama_provider: OllamaProvider | None = None,
        recovery_interval: float | None = None,
    ) -> None:
        self.hf_provider = hf_provider or HuggingFaceProvider()
        self.ollama_provider = ollama_provider or OllamaProvider()
        self.recovery_interval = recovery_interval or getattr(
            settings, "huggingface_health_check_interval_seconds", 20.0
        )

        self._mode = ProviderMode.ONLINE
        self._last_hf_check = 0.0
        self._last_ollama_check = 0.0
        self._hf_healthy = True
        self._ollama_healthy = False
        self._ollama_models: list[str] = []
        self._internet_available = True
        self._status_listeners: list[Callable[[dict[str, Any]], Awaitable[None]]] = []
        self._background_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def mode(self) -> ProviderMode:
        return self._mode

    @property
    def is_internet_available(self) -> bool:
        return self._internet_available

    @property
    def active_provider_name(self) -> str:
        if self._mode == ProviderMode.ONLINE:
            return "huggingface"
        elif self._mode in (ProviderMode.OFFLINE, ProviderMode.LOCAL_FALLBACK, ProviderMode.ONLINE_DEGRADED):
            return "ollama" if self._ollama_healthy else "huggingface"
        return "none"

    @property
    def active_provider(self) -> Any:
        name = self.active_provider_name
        if name == "ollama":
            return self.ollama_provider
        elif name == "huggingface":
            return self.hf_provider
        return None

    def add_status_listener(self, listener: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback for provider status changes."""
        if listener not in self._status_listeners:
            self._status_listeners.append(listener)

    def remove_status_listener(self, listener: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    async def _notify_listeners(self) -> None:
        payload = self.get_status_payload()
        for listener in list(self._status_listeners):
            try:
                await listener(payload)
            except Exception as e:
                logger.debug("status_listener_error", error=str(e))

    def get_status_payload(self) -> dict[str, Any]:
        """Generate structured status payload for WebSocket and REST APIs."""
        model_name: str | None = None
        if self.active_provider_name == "ollama":
            model_name = getattr(settings, "ollama_chat_model", "qwen3:1.7b")
        elif self.active_provider_name == "huggingface":
            model_name = "qwen-chat"
        else:
            model_name = None

        return {
            "mode": self._mode.value,
            "provider": self.active_provider_name,
            "model": model_name,
            "local_fallback": self._mode in (ProviderMode.LOCAL_FALLBACK, ProviderMode.OFFLINE, ProviderMode.OFFLINE_LOCAL),
            "internet": self._internet_available,
            "huggingface": {
                "available": self._hf_healthy,
            },
            "ollama": {
                "available": self._ollama_healthy,
                "model_available": self._ollama_healthy,
                "model": getattr(settings, "ollama_chat_model", "qwen3:1.7b"),
            },
        }

    async def check_internet(self) -> bool:
        """Probe general internet connectivity."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get("https://router.huggingface.co", follow_redirects=True)
                self._internet_available = res.status_code < 500
                return self._internet_available
        except Exception:
            # Fallback probe
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    res = await client.get("https://1.1.1.1", follow_redirects=True)
                    self._internet_available = res.status_code < 500
                    return self._internet_available
            except Exception:
                self._internet_available = False
                return False

    async def check_huggingface_health(self) -> bool:
        """Check if HuggingFace API is reachable and accepting requests."""
        if not self._internet_available:
            self._hf_healthy = False
            return False
        try:
            token = getattr(settings, "huggingface_api_token", "")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with httpx.AsyncClient(timeout=3.0, headers=headers) as client:
                # Lightweight check to HF router or models endpoint
                res = await client.get(
                    "https://router.huggingface.co/v1/models",
                    timeout=3.0,
                )
                self._hf_healthy = res.status_code in (200, 401, 403)  # 200 or auth check means service is up
                return self._hf_healthy
        except Exception:
            self._hf_healthy = False
            return False

    async def check_ollama_health(self) -> tuple[bool, str | None]:
        """Check if local Ollama daemon and target model are ready."""
        target_model = getattr(settings, "ollama_chat_model", "qwen3:1.7b")
        is_up, err, models = await self.ollama_provider.check_health(target_model)
        self._ollama_healthy = is_up
        self._ollama_models = models
        return is_up, err

    async def update_all_health(self) -> ProviderMode:
        """Run comprehensive health checks across internet, HF, and Ollama."""
        async with self._lock:
            old_mode = self._mode

            await self.check_internet()
            await self.check_ollama_health()

            if self._internet_available:
                await self.check_huggingface_health()

            if self._internet_available and self._hf_healthy:
                self._mode = ProviderMode.ONLINE
            elif not self._internet_available:
                if self._ollama_healthy:
                    self._mode = ProviderMode.OFFLINE
                else:
                    self._mode = ProviderMode.NO_PROVIDER
            else:  # Internet is up but HF is down/failing
                if self._ollama_healthy:
                    self._mode = ProviderMode.LOCAL_FALLBACK
                else:
                    self._mode = ProviderMode.NO_PROVIDER

            if self._mode != old_mode:
                logger.info(
                    "provider_mode_changed",
                    old_mode=old_mode.value,
                    new_mode=self._mode.value,
                    active_provider=self.active_provider_name,
                )
                await self._notify_listeners()

            return self._mode

    def record_hf_failure(self, reason: str = "request_failed") -> None:
        """Record a live HuggingFace failure and immediately trigger failover."""
        old_mode = self._mode
        self._hf_healthy = False
        if self._ollama_healthy:
            self._mode = ProviderMode.LOCAL_FALLBACK
        else:
            self._mode = ProviderMode.NO_PROVIDER

        logger.warning("huggingface_failed_failover_triggered", reason=reason, new_mode=self._mode.value)
        if self._mode != old_mode:
            asyncio.create_task(self._notify_listeners())

    def record_hf_success(self) -> None:
        """Record successful HF request."""
        self._hf_healthy = True
        self._internet_available = True
        if self._mode != ProviderMode.ONLINE:
            self._mode = ProviderMode.ONLINE
            asyncio.create_task(self._notify_listeners())

    async def start_background_monitor(self) -> None:
        """Start recurring background health check loop."""
        if self._background_task is not None and not self._background_task.done():
            return

        async def _monitor_loop() -> None:
            logger.info("provider_monitor_started", interval=self.recovery_interval)
            # Initial probe
            await self.update_all_health()

            while True:
                try:
                    await asyncio.sleep(self.recovery_interval)
                    # Periodic recovery test when degraded or fallback
                    if self._mode in (ProviderMode.LOCAL_FALLBACK, ProviderMode.OFFLINE, ProviderMode.NO_PROVIDER):
                        logger.debug("probing_huggingface_recovery")
                        await self.update_all_health()
                    else:
                        # Quick periodic verification
                        await self.check_ollama_health()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug("provider_monitor_loop_error", error=str(e))

        self._background_task = asyncio.create_task(_monitor_loop())

    def stop_background_monitor(self) -> None:
        if self._background_task is not None and not self._background_task.done():
            self._background_task.cancel()
            self._background_task = None
