from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field

from .config import settings


class OpenAIAdsContent(BaseModel):
    id: str
    name: str | None = None
    content_type: str = "product"
    quantity: int = Field(ge=1)
    amount: int | None = Field(default=None, ge=0)
    currency: str | None = None


class OpenAIAdsEvent(BaseModel):
    id: str
    type: str = "order_created"
    timestamp_ms: int
    data: dict[str, Any]
    oppref: str | None = None
    source_url: str | None = None
    action_source: str = "web"
    user: dict[str, Any] | None = None
    opt_out: bool = False


class OpenAIAdsEventsRequest(BaseModel):
    validate_only: bool = False
    integration_source: str | None = None
    events: list[OpenAIAdsEvent] = Field(min_length=1, max_length=1000)


class OpenAIAdsClient:
    """Server-side client for OpenAI Ads Conversions API."""

    _FORBIDDEN_USER_KEYS = {"email", "external_id", "phone", "phone_number"}

    def __init__(self) -> None:
        self.base_url = settings.openai_ads_base_url.rstrip("/")
        self.pixel_id = settings.openai_ads_pixel_id
        self.api_key = settings.openai_ads_conversions_api_key
        self.timeout = settings.openai_ads_timeout_seconds
        self.integration_source = settings.openai_ads_integration_source

    def _validate_config(self) -> None:
        if not self.pixel_id:
            raise RuntimeError("OPENAI_ADS_PIXEL_ID не задан")
        if not self.api_key:
            raise RuntimeError("OPENAI_ADS_CONVERSIONS_API_KEY не задан")

    @staticmethod
    def _validate_timestamp(timestamp: datetime) -> None:
        now = datetime.now(timezone.utc)
        event_time = timestamp.astimezone(timezone.utc)
        if event_time < now - timedelta(days=7):
            raise ValueError("timestamp события не может быть старше 7 дней")
        if event_time > now + timedelta(minutes=10):
            raise ValueError("timestamp события не может быть более чем на 10 минут в будущем")

    @staticmethod
    def _sanitize_source_url(source_url: str | None) -> str | None:
        if not source_url:
            return None
        parsed = urlsplit(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url должен быть абсолютным HTTP(S)-URL")
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))

    @classmethod
    def _validate_user(cls, user: dict[str, Any] | None) -> None:
        if not user:
            return
        leaked = cls._FORBIDDEN_USER_KEYS.intersection(user)
        if leaked:
            raise ValueError(
                "OpenAI Ads user data must not contain raw identity fields: "
                + ", ".join(sorted(leaked))
            )

    async def send_events(
        self,
        events: list[OpenAIAdsEvent],
        *,
        validate_only: bool | None = None,
    ) -> dict[str, Any]:
        # Validate the request contract before checking external integration
        # configuration. Invalid caller input must produce its own deterministic
        # validation error even when Ads credentials are absent in the environment.
        if not 1 <= len(events) <= 1000:
            raise ValueError("OpenAI Ads принимает от 1 до 1000 событий за запрос")
        for event in events:
            self._validate_user(event.user)
            if event.action_source == "web":
                event.source_url = self._sanitize_source_url(event.source_url)
                if not event.source_url:
                    raise ValueError("source_url обязателен для web-события")

        self._validate_config()

        request = OpenAIAdsEventsRequest(
            validate_only=settings.openai_ads_validate_only if validate_only is None else validate_only,
            integration_source=self.integration_source or None,
            events=events,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/events",
                params={"pid": self.pixel_id},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request.model_dump(exclude_none=True),
            )
            response.raise_for_status()
            return response.json()

    async def send_order_created(
        self,
        *,
        order_id: str,
        amount_minor: int,
        currency: str | None = None,
        contents: list[OpenAIAdsContent] | None = None,
        timestamp: datetime | None = None,
        oppref: str | None = None,
        source_url: str | None = None,
        user: dict[str, Any] | None = None,
        opt_out: bool = False,
        validate_only: bool | None = None,
    ) -> dict[str, Any]:
        if amount_minor < 0:
            raise ValueError("amount_minor не может быть отрицательным")

        event_time = timestamp or datetime.now(timezone.utc)
        self._validate_timestamp(event_time)
        event_source_url = self._sanitize_source_url(source_url or settings.openai_ads_source_url)
        self._validate_user(user)

        event_data: dict[str, Any] = {
            "type": "contents",
            "amount": amount_minor,
            "currency": (currency or settings.openai_ads_default_currency).upper(),
        }
        if contents:
            event_data["contents"] = [item.model_dump(exclude_none=True) for item in contents]

        event = OpenAIAdsEvent(
            id=order_id,
            type="order_created",
            timestamp_ms=int(event_time.timestamp() * 1000),
            oppref=oppref,
            source_url=event_source_url,
            action_source="web",
            user=user,
            opt_out=opt_out,
            data=event_data,
        )
        return await self.send_events([event], validate_only=validate_only)

    async def try_send_order_created(self, **kwargs: Any) -> bool:
        """Best-effort reporting that never blocks the business flow."""
        try:
            await self.send_order_created(**kwargs)
            return True
        except Exception:
            return False
