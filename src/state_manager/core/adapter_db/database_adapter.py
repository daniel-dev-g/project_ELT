from abc import ABC, abstractmethod


class DatabaseAdapter(ABC):
    @abstractmethod
    def get_engine(self, config: dict):
        pass

    @abstractmethod
    def check_bulk_permission(self, engine) -> bool:
        pass

    @abstractmethod
    def bulk_load(self, task: dict) -> int:
        """
            Executes bulk load from file to table.
            Returns number of inserted rows.
            Raises exception on technical failure.
        """
        pass
