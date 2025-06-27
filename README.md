# Cloud Storage Services Connector
A library that consolidates storage services of various cloud storage providers


## Project Purpose
Cloud Service Providers (CSP) such as Amazon AWS, Microsoft Azure, and Google GCP provide a cloud-based storage service that can be used to upload and download files as needed. In turn, storage services can be integrated into larger applications and used for the storage needs of the application. This allows applications to persist data in the cloud in an efficient, tolerant, and secure way. These storage services differ in, among other things, the storage capacities they offer, the performance of uploading/downloading files, and the prices they have. Furthermore, each service requires a separate interface in order to communicate with the storage backend making switching from one service to another quite cumbersome.

The purpose of this project is to, therefore, create a Python library that allows uploading,  downloading, and deleting files to/from any of the supported cloud storage providers through a common interface. The library should accommodate different authentication mechanisms required by the supported storage services and hide the implementation details of each storage provider.

The supported cloud storage providers are:
- **Dropbox**
- **Box**
- **Google Drive**
- **Amazon S3**

## Running Instructions
### Requirements
- Python 3+
- Free ports:
  - 8080 for running temporary server when authorising for Box using OAuth2

### Steps
1. **Install Dependencies** (from project root)
```bash
cd src
pip install -r requirements.txt
```
2. **Run Command** (from *src* folder)

A common command structure is used for all services, specifically:
```bash
python main.py <service> <operation> -rp <remote_path> -lp <local_path>
```
Where `<service>` can be any one of:
- **dropbox**
- **box**
- **gdrive**
- **s3**

And `<operation>` can be any one of:
- **download**
- **upload**
- **delete**

Finally:
- The `-lp` or `--local_path` option is used to specify the local file or directory (not required for **delete** operations)
- The `-rp` or `--remote_path` option is used to specify the remote directory or file (e.g. Dropbox folder where files will be uploaded)
- Help messages for any command are available using the `-h` or `--help` option

For example, to upload a local folder (called test) to Dropbox:
```bash
python main.py dropbox upload -lp ../../test -rp /
```

If the user has not previously authorised the library to access their data that is stored on a cloud provider, an OAuth2 flow will automatically start in the browser.

The only exception is **Amazon S3**, which requires additional setup. Before the library can interact with S3 buckets, authentication using the AWS CLI must be configured, as explained [here](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).
   
