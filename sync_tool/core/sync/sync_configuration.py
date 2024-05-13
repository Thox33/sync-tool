from typing import Dict

from pydantic import BaseModel

from sync_tool.core.sync.sync_rule import SyncRule


class SyncConfiguration(BaseModel):
    rules: Dict[str, SyncRule]

    def get_rule(self, rule_name: str) -> SyncRule | None:
        """Get the sync rule for a given rule name.

        Args:
            rule_name (str): Name of the sync rule to get.

        Returns:
            SyncRule: The sync rule.
            None: If the sync rule does not exist.
        """
        return self.rules.get(rule_name)
