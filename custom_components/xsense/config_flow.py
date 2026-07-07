"""Config flow for X-Sense Home Security integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from xsense import AsyncXSense
from xsense.exceptions import APIFailure, AuthFailed

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, email: str, password: str) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = AsyncXSense()
    try:
        await session.init()
        await session.login(email, password)
    except AuthFailed as ex:
        raise InvalidAuth(f"Login failed: {ex}") from ex
    except APIFailure as ex:
        raise CannotConnect(f"X-Sense API error: {ex}") from ex

    if not session.access_token:
        raise InvalidAuth

    return {"title": f"X-Sense {session.username}"}


class XSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for X-Sense Home Security."""

    VERSION = 1
    entry: config_entries.ConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            try:
                info = await validate_input(self.hass, email, password)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(email.lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication with X-Sense."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            try:
                await validate_input(self.hass, email, password)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                existing_entry = await self.async_set_unique_id(email.lower())
                if existing_entry and self.entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data={
                            **self.entry.data,
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                        },
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=self.entry.data[CONF_EMAIL]): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
