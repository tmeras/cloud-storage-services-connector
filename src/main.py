import argparse
import logging
import utils

import services.dropbox_implementation as dropbox
import services.box_implementation as box


def parse_arguments():
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
        "-lp", "--local_path", required=True, metavar="",
        help="path to local directory where content will be downloaded"
    )
    dbx_dlparser.add_argument(
        "-dp", "--dbx_path", required=True, metavar="",
        help="path to Dropbox file or directory that will be downloaded"
    )

    # Create subcommand for uploading to Dropbox
    dbx_uplparser = dbx_subparser.add_parser(
        "upload", help="upload content to Dropbox")
    dbx_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or directory that will be uploaded"
    )
    dbx_uplparser.add_argument(
        "-dp", "--dbx_path", required=True, metavar="", help="path to Dropbox directory where content will be uploaded"
    )

    # Create subcommand for deleting Dropbox content
    dbx_delparser = dbx_subparser.add_parser(
        "delete", help="delete Dropbox content")
    dbx_delparser.add_argument(
        "-dp", "--dbx_path", required=True, metavar="",
        help="path to Dropbox file or folder that will be deleted"
    )
    

    # Create subcommand for Box
    box_parser = subparsers.add_parser("box", help="use Box services")
    box_subparser = box_parser.add_subparsers(
        title="Box actions", required=True, dest="box_action")

    # Create subcommand for downloading from Box
    box_dlparser = box_subparser.add_parser(
        "download", help="download Box content")
    box_dlparser.add_argument(
        "-lp", "--local_path", required=True, metavar="",
        help="path to local directory where content will be downloaded"
    )
    box_dlparser.add_argument(
        "-bn", "--box_name", required=True, metavar="",
        help="name of Box content that will be downloaded"
    )

    # Create subcommand for uploading to Box
    box_uplparser = box_subparser.add_parser(
        "upload", help="upload content to Box")
    box_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or directory that will be uploaded"
    )
    box_uplparser.add_argument(
        "-dirn", "--directory_name", required=False, default="", metavar="", help="name of Box directory where content will be uploaded"
    )

    # Create subcommand for deleting Box content
    box_delparser = box_subparser.add_parser(
        "delete", help="delete Box content")
    box_delparser.add_argument(
        "-bn", "--box_name", required=True, metavar="", help="name of Box content that should be deleted"
    )


    # Create subcommand for Google Drive
    gdrive_parser = subparsers.add_parser(
        "gdrive", help="use Google Drive services")

    # Create subcommand for Amazon S3
    s3_parser = subparsers.add_parser("s3", help="use Amazon S3 services")

    # Create subcommand for Azure Blob storage
    blob_parser = subparsers.add_parser(
        "blob", help="use Azure Blob storage services")

    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    args = parse_arguments()
    logging.debug(args)

    if args.service == 'dropbox':
        dp = dropbox.Dropbox()
        if args.dbx_action == 'upload':
            dp.upload(args.local_path.strip(), args.dbx_path.strip())
        elif args.dbx_action == 'download':
            dp.download(args.local_path.strip(), args.dbx_path.strip())
        elif args.dbx_action == 'delete':
            dp.delete(args.dbx_path.strip())
        dp.close_dbx()
    elif args.service == 'box':
        bx = box.Box()
        if args.box_action == 'upload':
            bx.upload(args.local_path.strip(), args.directory_name.strip())
        elif args.box_action == 'download':
            bx.download(args.local_path.strip(), args.box_name.strip())
        elif args.box_action == 'delete':
            bx.delete(args.box_name.strip())
    else:
        utils.print_string(
            "Support for this service is not implemented yet", utils.PrintStyle.WARNING)
