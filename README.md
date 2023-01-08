# Cloud storage data connectors
A library that consolidates data connectors of various cloud storage providers


## Description
Cloud Service Providers (CSP) such as Amazon AWS, Microsoft Azure, and Google GCP provide a cloud-based storage service that can be used to upload and download files as needed. In turn, storage services can be integrated into larger applications and used for the storage needs of the application. This allows applications to persist data in the cloud in an efficient, tolerant, and secure way. These storage services differ in, among other things, the storage capacities they offer, the performance of uploading/downloading files, and the prices they have. Furthermore, each service requires a separate interface in order to communicate with the storage backend making switching from one service to another quite cumbersome.

The purpose of this project is to, therefore, create a Python library that allows uploading and downloading files to any of the supported cloud storage providers through a common interface. The library should accommodate different authentication mechanisms required by the supported storage services and hide the implementation details of each storage provider.


## Report

The report is using `LaTeX`.

### Generating the report

If you don't have `LaTeX` installed in your system do so by using

```bash
sudo apt install texlive-latex-base
sudo apt install texlive-fonts-recommended
sudo apt install texlive-fonts-extra
sudo apt install texlive-latex-extra
sudo apt install texlive-extra-utils
```

To generate the report use

```bash
cd report
make # the `Makefile` is provided
```

To remove auto-generated files you can use

```
make clean
```
