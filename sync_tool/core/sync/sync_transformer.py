from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class TransformerBase(BaseModel, metaclass=ABCMeta):
    """Base class for transformer implementations"""

    type: Any

    @abstractmethod
    def transform(self, data: Any) -> Any:
        """Transform the data.

        Args:
            data (Any): Data to transform.

        Returns:
            Any: Transformed data.

        Raises:
            ValueError: If transformation fails.
        """
        pass


class MappingTransformer(TransformerBase):
    """Transformer implementation that maps data from one value to another"""

    type: Literal["mapping"]
    map: Dict[Any, Any] = Field(default_factory=dict)

    def transform(self, data: Any) -> Any:
        """Transform the data"""

        if data not in self.map:
            raise ValueError(f"Could not find mapping for data {data}")

        return self.map[data]


Transformers = MappingTransformer


def create_transformer(**kwargs: Any) -> TransformerBase:
    """Create a transformer instance from the configuration

    Args:
        kwargs (Any): Configuration of the raw transformer

    Returns:
        TransformerBase: Transformer instance

    Raises:
        ValueError: If transformer type is unknown
    """
    if kwargs["type"] == "mapping":
        return MappingTransformer(**kwargs)

    raise ValueError(f"Unknown transformer type {kwargs['type']}")
