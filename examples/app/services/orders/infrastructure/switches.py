from app.core.cache.ttl_cache import TtlCache


class ParameterOrderSwitches:
    def __init__(self, parameters: TtlCache, paused_parameter: str) -> None:
        self._parameters = parameters
        self._paused_parameter = paused_parameter

    def ordering_paused(self) -> bool:
        return self._parameters.get(self._paused_parameter) == "true"
