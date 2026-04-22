from abc import ABC, abstractmethod
from sqlalchemy.engine import Engine


class DatabaseAdapter(ABC):
    engine: Engine

    @abstractmethod
    def get_engine(self, config: dict) -> Engine:
        pass

    @abstractmethod
    def check_bulk_permission(self) -> bool:
        pass

    @abstractmethod
    def bulk_load(self, task: dict) -> int:
        """
            Executes bulk load from file to table.
            Returns number of inserted rows.
            Raises exception on technical failure.
        """
        pass
