"""Create polished Google Docs from a styled .docx (Drive convert — no Docs API required)."""

from __future__ import annotations

import os
import re

from googleapiclient.http import MediaInMemoryUpload

from config import Cutoffs
from google_auth import get_drive_service
from processor import StudentData
from styled_doc import build_feedback_docx_bytes


def _safe_title(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", name).strip()
    return cleaned[:120] or "Student Feedback"


def create_feedback_doc(
    student: StudentData,
    analysis: dict,
    cutoffs: Cutoffs,
) -> dict:
    """
    Build a sample-style Word doc and upload+convert to Google Docs via Drive.
    Returns {document_id, url, title, user_id}.
    """
    drive = get_drive_service()
    title = f"Assessment Feedback — {_safe_title(student.user_name)}"
    docx_bytes = build_feedback_docx_bytes(student, analysis, cutoffs)

    metadata: dict = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    folder_id = os.environ.get("GOOGLE_OUTPUT_FOLDER_ID", "").strip()
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaInMemoryUpload(
        docx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        resumable=False,
    )
    created = (
        drive.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink, name",
            supportsAllDrives=True,
        )
        .execute()
    )
    doc_id = created["id"]
    url = created.get("webViewLink") or f"https://docs.google.com/document/d/{doc_id}/edit"
    return {
        "document_id": doc_id,
        "url": url,
        "title": created.get("name") or title,
        "user_id": student.user_id,
    }
