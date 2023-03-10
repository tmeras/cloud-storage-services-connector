from abc import ABCMeta, abstractmethod


class DataServiceError(Exception):
    pass


class DataService(metaclass=ABCMeta):
    @classmethod
    def build(cls, service_name):
        from .dropbox_implementation import Dropbox
        from .box_implementation import Box
        from .s3_implementation import S3
        from .gdrive_implementation import Gdrive

        if service_name == 'dropbox':
            service = Dropbox()
        elif service_name == 'box':
            service = Box()
        elif service_name == 'gdrive':
            service = Gdrive()
        elif service_name == 's3':
            service = S3()
        else:
            raise DataServiceError("Unsupported service '%s'" % service_name)
        return service

    def execute_action(self, args):
        if args.action == 'upload':
            self.upload(args.local_path.strip(), args.remote_path.strip())
        elif args.action == 'download':
            self.download(args.local_path.strip(), args.remote_path.strip())
        elif args.action == 'delete':
            self.delete(args.remote_path.strip())

    @abstractmethod
    def download(self, local_dir, path):
        """
        Downloads contents from cloud storage services
        """

    @abstractmethod
    def upload(self, local_dir, path):
        """
        Uploads contents to cloud storage services
        """

    @abstractmethod
    def delete(self, path):
        """
        Deletes content stored in cloud storage services
        """

    @abstractmethod
    def close(self):
        """
        Closes handler, clearing up resources.
        """
