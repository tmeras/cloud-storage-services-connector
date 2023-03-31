import argparse
import logging
import sys
import utils
import json
import services.data_service as ds


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.description = "A library that provides access to cloud storage services" \
                         "through a common interface for various cloud services"

    subparsers = parser.add_subparsers(
        title="available providers",
        required=True, dest="service"
    )

    # Create subcommand for Dropbox
    dbx_parser = subparsers.add_parser("dropbox", help="use Dropbox services")
    dbx_subparser = dbx_parser.add_subparsers(
        title="Dropbox actions", required=True, dest='action'
    )

    # Create subcommand for downloading from Dropbox
    dbx_dlparser = dbx_subparser.add_parser(
        "download", help="download Dropbox content"
    )
    dbx_dlparser.add_argument(
        "-lp", "--local_path", required=True, metavar="",
        help="path to local directory where content will be downloaded"
    )
    dbx_dlparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="",
        help="path to Dropbox file or directory that will be downloaded"
    )

    # Create subcommand for uploading to Dropbox
    dbx_uplparser = dbx_subparser.add_parser(
        "upload", help="upload content to Dropbox"
    )
    dbx_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or directory that will be uploaded"
    )
    dbx_uplparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="", help="path to Dropbox directory where content will be uploaded"
    )

    # Create subcommand for deleting Dropbox content
    dbx_delparser = dbx_subparser.add_parser(
        "delete", help="delete Dropbox content"
    )
    dbx_delparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="",
        help="path to Dropbox content that will be deleted"
    )

    # Create subcommand for Box
    box_parser = subparsers.add_parser("box", help="use Box services")
    box_subparser = box_parser.add_subparsers(
        title="Box actions", required=True, dest="action")

    # Create subcommand for downloading from Box
    box_dlparser = box_subparser.add_parser(
        "download", help="download Box content"
    )
    box_dlparser.add_argument(
        "-lp", "--local_path", required=True, metavar="",
        help="path to local directory where content will be downloaded"
    )
    box_dlparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="",
        help="path to Box content that will be downloaded"
    )

    # Create subcommand for uploading to Box
    box_uplparser = box_subparser.add_parser(
        "upload", help="upload content to Box"
    )
    box_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or directory that will be uploaded"
    )
    box_uplparser.add_argument(
        "-rp", "--remote_path", required=False, default="", metavar="",
        help="path to Box directory where content will be uploaded; leave empty to upload to root directory "
    )

    # Create subcommand for deleting Box content
    box_delparser = box_subparser.add_parser(
        "delete", help="delete Box content")
    box_delparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="", help="path to Box content that will be deleted"
    )

    # Create subcommand for Google Drive
    gdrive_parser = subparsers.add_parser(
        "gdrive", help="use Google Drive services")
    gdrive_subparser = gdrive_parser.add_subparsers(title="Google Drive actions", required=True, dest="action")

    # Create subcommand for downloading from Drive
    gdrive_dlparser = gdrive_subparser.add_parser("download", help="download Drive content")
    gdrive_dlparser.add_argument("-lp", "--local_path", required=True, metavar="",
                                 help="path to local directory where content will be downloaded")
    gdrive_dlparser.add_argument("-rp", "--remote_path", required=True, metavar="",
                                 help="path to Drive content that will be downloaded")

    # Create subcommand for uploading to Drive
    gdrive_uplparser = gdrive_subparser.add_parser("upload", help="upload content to Drive")
    gdrive_uplparser.add_argument("-lp", "--local_path", required=True, metavar="",
                                  help="path to local file or directory that will be uploaded")
    gdrive_uplparser.add_argument("-rp", "--remote_path", required=False, default="", metavar="",
                                  help="path to Drive directory where content will be uploaded; leave empty to upload to root directory")

    # Create subcommand for deleting Drive content
    gdrive_delparser = gdrive_subparser.add_parser("delete", help="delete Drive content")
    gdrive_delparser.add_argument("-rp", "--remote_path", help="path to Drive content that will be deleted")

    # Create subcommand for Amazon S3
    s3_parser = subparsers.add_parser("s3", help="use Amazon S3 services")
    s3_subparser = s3_parser.add_subparsers(
        title="S3 actions", required=True, dest="action")

    # Create subcommand for downloading from S3
    s3_dlparser = s3_subparser.add_parser(
        "download", help="download S3 content"
    )
    s3_dlparser.add_argument(
        "-lp", "--local_path", required=True, metavar="",
        help="path to local directory where content will be downloaded"
    )
    s3_dlparser.add_argument(
        "-rp", "--remote_path", required=True,
        metavar="", help="path to S3 content that will be downloaded"
    )

    # Create subcommand for uploading to S3
    s3_uplparser = s3_subparser.add_parser(
        "upload", help="upload content to S3"
    )
    s3_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="",
        help="path to local file or directory that will be uploaded"
    )
    s3_uplparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="",
        help="S3 path where content will be uploaded"
    )

    # Create subcommand for deleting S3 content
    s3_delparser = s3_subparser.add_parser("delete", help="delete S3 content")
    s3_delparser.add_argument(
        "-rp", "--remote_path", required=True, metavar="",
        help="path to S3 content that will be deleted"
    )

    # Create subcommand for Azure Blob storage
    blob_parser = subparsers.add_parser(
        "blob", help="use Azure Blob storage services"
    )

    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    args = parse_arguments()
    logging.debug(args)

    try:
        service = ds.DataService.build(args.service)
    except ds.DataServiceError as dse:
        utils.print_string(
            "Support for service '%s' is not implemented yet" % args.service,
            utils.PrintStyle.WARNING
        )
        sys.exit(0)

    service.execute_action(args)
    service.close() 
