"""Google Sheets read/write — swappable later for a DB data source."""

from __future__ import annotations

import re

from google_auth import get_sheets_service


def extract_spreadsheet_id(sheet_url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url.strip())
    if not match:
        raise ValueError(f"Could not parse spreadsheet id from URL: {sheet_url}")
    return match.group(1)


def read_sheet_as_dicts(sheet_url: str, sheet_name: str) -> list[dict[str, str]]:
    """Read a tab into list of row dicts keyed by header names. Does not modify the sheet."""
    spreadsheet_id = extract_spreadsheet_id(sheet_url)
    sheets = get_sheets_service()
    result = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'")
        .execute()
    )
    values = result.get("values", [])
    if not values:
        raise ValueError(f"Sheet '{sheet_name}' is empty")

    headers = [str(h).strip() for h in values[0]]
    rows: list[dict[str, str]] = []
    for raw in values[1:]:
        row: dict[str, str] = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            row[header] = str(raw[i]).strip() if i < len(raw) else ""
        if any(row.values()):
            rows.append(row)
    return rows


def ensure_unique_sheet_title(spreadsheet_id: str, base_title: str) -> str:
    sheets = get_sheets_service()
    meta = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if base_title not in existing:
        return base_title
    n = 2
    while f"{base_title} ({n})" in existing:
        n += 1
    return f"{base_title} ({n})"


def write_new_subsheet(
    sheet_url: str,
    title: str,
    headers: list[str],
    rows: list[list[str]],
) -> str:
    """Create a new tab and write header + data. Returns the final tab title."""
    spreadsheet_id = extract_spreadsheet_id(sheet_url)
    sheets = get_sheets_service()
    final_title = ensure_unique_sheet_title(spreadsheet_id, title)

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": final_title}}}]},
    ).execute()

    values = [headers] + rows
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{final_title}'!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    return final_title
