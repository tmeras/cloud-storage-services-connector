import argparse
import logging
import utils
import services.data_service 

import services.dropbox_implementation as dropbox
import services.box_implementation as box
import services.s3_implementation as s3
import services.gdrive_implementation as gdrive


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
        "-dbxp", "--dbx_path", required=True, metavar="",
        help="path to Dropbox content that will be deleted"
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
        "-bxp", "--box_path", required=True, metavar="",
        help="path to Box content that will be downloaded"
    )

    # Create subcommand for uploading to Box
    box_uplparser = box_subparser.add_parser(
        "upload", help="upload content to Box")
    box_uplparser.add_argument(
        "-lp", "--local_path", required=True, metavar="", help="path to local file or directory that will be uploaded"
    )
    box_uplparser.add_argument(
        "-dir", "--directory_path", required=False, default="", metavar="",
        help="path to Box directory where content will be uploaded; leave empty to upload to root directory "
    )

    # Create subcommand for deleting Box content
    box_delparser = box_subparser.add_parser(
        "delete", help="delete Box content")
    box_delparser.add_argument(
        "-bxp", "--box_path", required=True, metavar="", help="path to Box content that will be deleted"
    )

    # Create subcommand for Google Drive
    gdrive_parser = subparsers.add_parser(
        "gdrive", help="use Google Drive services")
    gdrive_subparser = gdrive_parser.add_subparsers(title="Google Drive actions", required=True, dest="gdrive_action")

    # Create subcommand for downloading from Drive
    gdrive_dlparser = gdrive_subparser.add_parser("download", help="download Drive content")
    gdrive_dlparser.add_argument("-lp", "--local_path", required=True, metavar="",
                                 help="path to local directory where content will be downloaded")
    gdrive_dlparser.add_argument("-dp", "--drive_path", required=True, metavar="",
                                 help="path to Drive content that will be downloaded")

    # Create subcommand for uploading to Drive
    gdrive_uplparser = gdrive_subparser.add_parser("upload", help="upload content to Drive")
    gdrive_uplparser.add_argument("-lp", "--local_path", required=True, metavar="",
                                  help="path to local file or directory that will be uploaded")
    gdrive_uplparser.add_argument("-dirp", "--directory_path", required=False, default="", metavar="",
                                  help="path to Drive directory where content will be uploaded; leave empty to upload to root directory")

    # Create subcommand for deleting Drive content
    gdrive_delparser = gdrive_subparser.add_parser("delete", help="delete Drive content")
    gdrive_delparser.add_argument("-dp", "--drive_path", help="path to Drive content that will be deleted")

    # Create subcommand for Amazon S3
    s3_parser = subparsers.add_parser("s3", help="use Amazon S3 services")
    s3_subparser = s3_parser.add_subparsers(
        title="S3 actions", required=True, dest="s3_action")

    # Create subcommand for downloading from S3
    s3_dlparser = s3_subparser.add_parser(
        "download", help="download S3 content")
    s3_dlparser.add_argument("-lp", "--local_path", required=True, metavar="",
                             help="path to local directory where content will be downloaded")
    s3_dlparser.add_argument("-s3p", "--s3_path", required=True,
                             metavar="", help="path to S3 content that will be downloaded")

    # Create subcommand for uploading to S3
    s3_uplparser = s3_subparser.add_parser(
        "upload", help="upload content to S3")
    s3_uplparser.add_argument("-lp", "--local_path", required=True, metavar="",
                              help="path to local file or directory that will be uploaded")
    s3_uplparser.add_argument("-s3p", "--s3_path", required=True, metavar="",
                              help="S3 path where content will be uploaded")

    # Create subcommand for deleting S3 content
    s3_delparser = s3_subparser.add_parser("delete", help="delete S3 content")
    s3_delparser.add_argument("-s3p", "--s3_path", required=True, metavar="", help="path to S3 content that will be deleted")


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
            bx.upload(args.local_path.strip(), args.directory_path.strip())
        elif args.box_action == 'download':
            bx.download(args.local_path.strip(), args.box_path.strip())
        elif args.box_action == 'delete':
            bx.delete(args.box_path.strip())
    elif args.service == 'gdrive':
        gd = gdrive.Gdrive()
        if args.gdrive_action == 'upload':
            gd.upload(args.local_path.strip(), args.directory_path.strip())
        elif args.gdrive_action == 'download':
            gd.download(args.local_path.strip(), args.drive_path.strip())
        elif args.gdrive_action == 'delete':
            gd.delete(args.drive_path.strip())
    elif args.service == 's3':
        s3 = s3.S3()
        if args.s3_action == 'upload':
            s3.upload(args.local_path.strip(), args.s3_path.strip())
        elif args.s3_action == 'download':
            s3.download(args.local_path.strip(), args.s3_path.strip())
        elif args.s3_action == 'delete':
            s3.delete(args.s3_path.strip())
    else:
        utils.print_string(
            "Support for this service is not implemented yet", utils.PrintStyle.WARNING)
