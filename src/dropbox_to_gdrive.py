"""Utilities to migrate files from Dropbox to Google Drive."""
from __future__ import annotations

import argparse
import io
import logging
import mimetypes
import os
from pathlib import PurePosixPath
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

import dropbox
from dropbox.files import FileMetadata, FolderMetadata
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials as ServiceAccountCredentials


LOGGER = logging.getLogger(__name__)
DEFAULT_SCOPES = ("https://www.googleapis.com/auth/drive",)
FOLDER_MIME = "application/vnd.google-apps.folder"
DEFAULT_FILE_MIME = "application/octet-stream"


class DropboxClient:
    """Wrapper around the Dropbox SDK that exposes a small API surface."""

    def __init__(self, token: str) -> None:
        self._client = dropbox.Dropbox(token)

    def iterate_folder(self, path: str) -> Iterator[dropbox.files.Metadata]:
        """Yield entries under *path* recursively."""
        path = path.strip()
        if path == "/":
            path = ""
        LOGGER.debug("Listing Dropbox path %s", path or "<root>")
        result = self._client.files_list_folder(path, recursive=True)
        yield from result.entries
        while result.has_more:
            result = self._client.files_list_folder_continue(result.cursor)
            yield from result.entries

    def download_file(self, path: str) -> bytes:
        LOGGER.debug("Downloading Dropbox file %s", path)
        metadata, response = self._client.files_download(path)
        if not isinstance(metadata, FileMetadata):
            raise ValueError(f"Expected file metadata when downloading {path}")
        return response.content


@dataclass
class GoogleDriveClient:
    """Small helper wrapper around the Google Drive API."""

    credentials_file: str
    scopes: Iterable[str] = DEFAULT_SCOPES

    def __post_init__(self) -> None:
        creds = ServiceAccountCredentials.from_service_account_file(
            self.credentials_file, scopes=list(self.scopes)
        )
        self._service = build("drive", "v3", credentials=creds)

    def ensure_folder(self, name: str, parent_id: str) -> str:
        existing = self._find_item(name=name, parent_id=parent_id, mime_type=FOLDER_MIME)
        if existing:
            return existing["id"]
        LOGGER.info("Creating Google Drive folder %s under %s", name, parent_id)
        body = {
            "name": name,
            "mimeType": FOLDER_MIME,
            "parents": [parent_id],
        }
        folder = (
            self._service.files()
            .create(body=body, supportsAllDrives=True, fields="id")
            .execute()
        )
        return folder["id"]

    def upload_file(
        self, name: str, parent_id: str, data: bytes, mime_type: Optional[str]
    ) -> None:
        existing = self._find_item(name=name, parent_id=parent_id, mime_type=None)
        if existing and existing.get("mimeType") != FOLDER_MIME:
            LOGGER.info("Skipping upload for %s - file already exists on Drive", name)
            return
        effective_mime = mime_type or DEFAULT_FILE_MIME
        media = MediaIoBaseUpload(
            io.BytesIO(data), mimetype=effective_mime, resumable=False
        )
        body = {"name": name, "parents": [parent_id]}
        LOGGER.info("Uploading %s to Google Drive folder %s", name, parent_id)
        (
            self._service.files()
            .create(body=body, media_body=media, supportsAllDrives=True)
            .execute()
        )

    def ensure_path(self, path: str, root_id: str = "root") -> str:
        parts = [part for part in path.split("/") if part]
        parent = root_id
        for part in parts:
            parent = self.ensure_folder(name=part, parent_id=parent)
        return parent

    def _find_item(
        self, name: str, parent_id: str, mime_type: Optional[str]
    ) -> Optional[dict]:
        safe_name = name.replace("'", "\\'")
        query_parts = [
            f"name = '{safe_name}'",
            f"'{parent_id}' in parents",
            "trashed = false",
        ]
        if mime_type:
            query_parts.append(f"mimeType = '{mime_type}'")
        query = " and ".join(query_parts)
        response = (
            self._service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name, mimeType)",
                pageSize=1,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        files = response.get("files", [])
        return files[0] if files else None


class DropboxToDriveMigrator:
    def __init__(
        self, dropbox_client: DropboxClient, drive_client: GoogleDriveClient
    ) -> None:
        self._dropbox = dropbox_client
        self._drive = drive_client

    def migrate(self, dropbox_path: str = "", drive_path: str = "") -> None:
        base = dropbox_path.strip().rstrip("/")
        drive_parent = self._drive.ensure_path(drive_path) if drive_path else "root"

        for entry in self._dropbox.iterate_folder(base or ""):
            if isinstance(entry, FolderMetadata):
                relative = self._relative_path(entry.path_display, base)
                if not relative:
                    continue
                self._drive.ensure_path(relative, root_id=drive_parent)
            elif isinstance(entry, FileMetadata):
                relative = self._relative_path(entry.path_display, base)
                parent_path, _, filename = relative.rpartition("/")
                target_parent = (
                    self._drive.ensure_path(parent_path, root_id=drive_parent)
                    if parent_path
                    else drive_parent
                )
                data = self._dropbox.download_file(entry.path_lower)
                mime_type, _ = mimetypes.guess_type(filename)
                try:
                    self._drive.upload_file(filename, target_parent, data, mime_type)
                except HttpError as exc:
                    LOGGER.error("Failed to upload %s: %s", filename, exc)
            else:
                LOGGER.warning(
                    "Skipping unsupported Dropbox entry type: %s", type(entry)
                )

    @staticmethod
    def _relative_path(path_display: str, base: str) -> str:
        relative = path_display.lstrip("/")
        if base:
            base_norm = base.lstrip("/")
            if base_norm:
                base_parts = PurePosixPath(base_norm).parts
                relative_parts = PurePosixPath(relative).parts
                if len(relative_parts) >= len(base_parts) and all(
                    rel_part.lower() == base_part.lower()
                    for base_part, rel_part in zip(base_parts, relative_parts)
                ):
                    remaining = relative_parts[len(base_parts) :]
                    relative = "/".join(remaining)
        return relative


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate files from Dropbox to Google Drive"
    )
    parser.add_argument("dropbox_token", help="Dropbox API token")
    parser.add_argument(
        "google_credentials",
        help="Path to Google service account credentials JSON",
    )
    parser.add_argument(
        "--dropbox-path",
        default="",
        help="Optional Dropbox folder path to migrate (defaults to the entire account)",
    )
    parser.add_argument(
        "--drive-path",
        default="",
        help="Optional Google Drive folder path where files will be uploaded",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    dropbox_client = DropboxClient(token=args.dropbox_token)
    drive_client = GoogleDriveClient(credentials_file=args.google_credentials)
    migrator = DropboxToDriveMigrator(dropbox_client, drive_client)
    migrator.migrate(dropbox_path=args.dropbox_path, drive_path=args.drive_path)


if __name__ == "__main__":
    main()
