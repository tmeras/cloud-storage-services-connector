from abc import ABCMeta, abstractmethod

class DataService(metaclass=ABCMeta):
    @abstractmethod
    def download(self, localdir, path):
        """
        Abstract method for downloading content from cloud storage services
        """
        pass
    
    @abstractmethod
    def upload(self,localdir,path):
        """
        Abstract method for uploading content to cloud storage services
        """
        pass

    @abstractmethod
    def delete(self,path):
        """
        Abstract method for deleting content stored in cloud storage services
        """
        pass