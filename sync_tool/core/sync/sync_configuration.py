from typing import Dict

from pydantic import BaseModel

from sync_tool.core.sync.sync_rule import SyncRule


class SyncConfiguration(BaseModel):
    rules: Dict[str, SyncRule]
