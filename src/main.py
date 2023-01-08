import argparse
import services.dropbox_implementation as dropbox_implementation

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.description = "A library that provides access to cloud storage services" \
        "through a common interface for various cloud services"

    subparsers = parser.add_subparsers(title="available providers",
                                       required=True, dest="service")

    # Create subcommand for Dropbox
    dbx_parser = subparsers.add_parser("dropbox", help="use Dropbox services")
    dbx_subparser = dbx_parser.add_subparsers(
        title="Dropbox actions", required=True, dest='dbx_action')

    # Create subcommand for downloading from Dropbox
    dbx_dlparser = dbx_subparser.add_parser(
        "download", help="download Dropbox content")
    dbx_dlparser.add_argument(
        "-f", "--is_file", action="store_true", help="specify if local_path points to file")
    dbx_dlparser.add_argument("-n", "--name", required=True, metavar="",
                              help="name of file (include extension) or zipped folder where content will be downloaded")
    dbx_dlparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or folder where content will be downloaded")
    dbx_dlparser.add_argument(
        "-dp", "--dbx_path", required=True, metavar="", help="path to Dropbox file or folder that will be downloaded")

    # Create subcommand for uploading to Dropbox
    dbx_uplparser = dbx_subparser.add_parser(
        "upload", help="upload content to Dropbox")
    dbx_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or folder that will be uploaded")
    dbx_uplparser.add_argument(
        "-dp", "--dbx_path", required=True, metavar="", help="path to Dropbox folder where content will be uploaded")

    # Create subcommand for deleting Dropbox content
    dbx_delparser = dbx_subparser.add_parser(
        "delete", help="delete Dropbox content")
    dbx_delparser.add_argument(
        "-dp", "--dbx_path", required=True, metavar="", help="path to Dropbox file or folder that will be deleted")

    # Create subcommand for Box
    box_parser = subparsers.add_parser("box", help="use Box services")

    # Create subcommand for Google Drive
    gdrive_parser = subparsers.add_parser(
        "gdrive", help="use Google Drive services")

    # Create subcommand for Amazon S3
    s3_parser = subparsers.add_parser("s3", help="use Amazon S3 services")

    # Create subcommand for Azure Blob storage
    blob_parser = subparsers.add_parser(
        "blob", help="use Azure Blob storage services")

    args = parser.parse_args()
    print(args)

    if args.service == 'dropbox':
        if args.dbx_action == 'upload':
            dropbox_implementation.upload(args.local_path, args.dbx_path)
        elif args.dbx_action == 'download':
            dropbox_implementation.download(
                args.is_file, args.name, args.local_path, args.dbx_path)
        elif args.dbx_action == 'delete':
            dropbox_implementation.delete(args.dbx_path)
        dropbox_implementation.close_dbx()
    else:
        print("Support for this service is not implemented yet")
