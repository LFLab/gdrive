import json
from pprint import pprint
from pathlib import Path
from argparse import ArgumentParser

from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials


SECRETS_FILE, CREDENTIAL_FILE = "client_secret.json", "credentials.json"
API_SERVICE_NAME, API_VERSION = "drive", "v3"

# ref: https://developers.google.com/drive/api/v3/about-auth
SCOPES = ("https://www.googleapis.com/auth/drive", )


class GDriveAPI:
    def __init__(self, creds, scopes=SCOPES, *,
                 api_name=API_SERVICE_NAME, version=API_VERSION):
        if not isinstance(creds, Credentials):
            self.creds = Credentials.from_authorized_user_info(creds, scopes)
        else:
            self.creds = creds
        self.service = build(api_name, version, credentials=self.creds)

    @classmethod
    def from_credential_file(cls, filename, scopes=SCOPES, *,
                             api_name=API_SERVICE_NAME, version=API_VERSION):
        with open(filename, 'r', encoding='utf8') as fp:
            credential = json.load(fp)
        return cls(credential, scopes, api_name=api_name, version=version)

    @classmethod
    def from_secret_file(cls, filename, scopes=SCOPES, port=8080, *,
                         api_name=API_SERVICE_NAME, version=API_VERSION):
        flow = InstalledAppFlow.from_client_secrets_file(filename, scopes)
        credentials = flow.run_local_server(port=port)
        return cls(credentials, scopes, api_name=api_name, version=version)

    def save_credentials(self, filename=CREDENTIAL_FILE):
        with open(filename, 'w', encoding='utf8') as fp:
            json.dump(self.creds.to_json(), fp)

    def create_folder(self, name):
        meta = dict(name=name, mimeType='application/vnd.google-apps.folder')
        file = self.service.files().create(body=meta, fields='id').execute()
        return file.get('id')

    def upload_file(self, filename, folder_id=None, rename_to=None):
        fpath = Path(filename)
        file_metadata = dict(name=rename_to or fpath.name, parents=[folder_id])
        media = MediaFileUpload(fpath.as_posix(), resumable=True)
        file = self.service.files().create(body=file_metadata,
                                           media_body=media,
                                           fields='id').execute()
        return file.get('id')

    def delete_file(self, file_id):
        return self.service.files().delete(fileId=file_id).execute()

    def query_files(self, name_contains, order_by='createdTime'):
        #ref: https://developers.google.com/resources/api-libraries/documentation/drive/v3/python/latest/drive_v3.files.html#list
        qs = f"name contains {name_contains!r}"
        r = self.service.files().list(q=qs, fields="files(id, name)",
                                      orderBy=order_by).execute()
        return [(f.get('id'), f.get('name')) for f in r.get('files', [])]


def main(args):
    if args.log:
        import logging
        log = logging.getLogger()
        log.setLevel(logging.INFO)

    if args.sub_command == 'auth':
        drive = GDriveAPI.from_secret_file(args.secret, port=args.port)
        drive.save_credentials(args.creds)

    drive = GDriveAPI.from_credential_file(args.creds)
    meths = dict(create=drive.create_folder, delete=drive.delete_file,
                 query=drive.query_files, upload=drive.upload_file)

    kws = dict(args._get_kwargs())
    kws.pop("log"), kws.pop("creds")
    meth = meths[kws.pop("sub_command")]
    pprint(meth(**kws))


if __name__ == '__main__':
    arg = ArgumentParser(prog="gdrive", description=__doc__)
    arg.add_argument("-l", "--log", action="store_true",
                     help=r"Enable the Logging module to show logs.")

    subdoc = r"Credential file is required before create/delete/query/upload ."
    subarg = arg.add_subparsers(required=True, dest='sub_command', help=subdoc)

    auth = subarg.add_parser("auth")
    auth.add_argument("-s", default=SECRETS_FILE, metavar="SecretFile",
                      dest="secret",
                      help=r"Input a secret file from your Google App."
                      f"  (Default: {SECRETS_FILE!r})")
    auth.add_argument("-o", default=CREDENTIAL_FILE, metavar="CredentialFile",
                      dest="creds",
                      help=r"Output an authorized user credentials."
                      f"  (Default: {CREDENTIAL_FILE!r})")
    auth.add_argument("-p", "--port", default=8080,
                      help=r"An local web server will be launched while"
                      " authenicating, change it if needed. (Default: 8080)")

    create = subarg.add_parser("create")
    create.add_argument("name",metavar="FolderName",
                        help=r"Create `FolderName` on your Google Drive.")
    create.add_argument("-c", metavar="CredentialFile", default=CREDENTIAL_FILE,
                        dest="creds", help=r"Authenicated credential file.")

    delete = subarg.add_parser("delete")
    delete.add_argument("file_id", metavar="FileID",
                        help=r"Delete specific file.")
    delete.add_argument("-c", metavar="CredentialFile", default=CREDENTIAL_FILE,
                        dest="creds", help=r"Authenicated credential file.")

    query = subarg.add_parser("query")
    query.add_argument("name_contains", metavar="FileName",
                       help=r"Query Files which contains the `name`.")
    query.add_argument("-c", metavar="CredentialFile", default=CREDENTIAL_FILE,
                        dest="creds", help=r"Authenicated credential file.")

    upload = subarg.add_parser("upload")
    upload.add_argument("filename")
    upload.add_argument("-t", "--rename", dest="rename_to",
                        help=r"Upload the file with a new name.")
    upload.add_argument("-p", metavar="folderId", dest="folder_id",
                        help=r"Upload the file into specific folder.")
    upload.add_argument("-c", metavar="CredentialFile", default=CREDENTIAL_FILE,
                        dest="creds", help=r"Authenicated credential file.")

    main(arg.parse_args())
