from typing import Optional


class AdapterInitError(Exception):
    """Should be raised if the initialization of an adapter fails."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(f"[Adapter Init] {message or 'Adapter initialization failed'}")


class AdapterTeardownError(Exception):
    """Should be raised if the teardown of an adapter fails."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(f"[Adapter Teardown] {message or 'Adapter teardown failed'}")
