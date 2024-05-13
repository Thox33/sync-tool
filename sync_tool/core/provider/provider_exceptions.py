from typing import Optional


class ProviderInitError(Exception):
    """Should be raised if the initialization of an provider fails."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(f"[Provider Init] {message or 'Provider initialization failed'}")


class ProviderGetDataError(Exception):
    """Should be raised if get_data of an provider fails."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(f"[Provider GetData] {message or 'Provider GetData failed'}")


class ProviderTeardownError(Exception):
    """Should be raised if the teardown of an provider fails."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(f"[Provider Teardown] {message or 'Provider teardown failed'}")
