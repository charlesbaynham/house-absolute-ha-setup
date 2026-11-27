from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_COLLECT_S, CONF_CONFIDENT_DB, CONF_MATCH_S, CONF_MAX_AGE_S, DEFAULTS, DOMAIN


class WhistleConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="Whistle", data={})

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return WhistleOptionsFlow()


class WhistleOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**DEFAULTS, **self.config_entry.options}
        number = vol.All(vol.Coerce(float), vol.Range(min=0))
        schema = vol.Schema({vol.Required(k, default=current[k]): number for k in
                             (CONF_COLLECT_S, CONF_MATCH_S, CONF_CONFIDENT_DB, CONF_MAX_AGE_S)})
        return self.async_show_form(step_id="init", data_schema=schema)
