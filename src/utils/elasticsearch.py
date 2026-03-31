from abc import ABC, abstractmethod


class AbsstractElasticsearchManager(ABC):

    @abstractmethod
    async def get_obj():
        pass

    @abstractmethod
    async def create_obj():
        pass

    @abstractmethod
    async def update_obj():
        pass

    @abstractmethod
    async def delete_obj():
        pass


class ElasticsearchManager(AbsstractElasticsearchManager):
    pass