"""
integrations.google.sheets — Google Sheets Service Integration (V8)

Provides direct async integration with Google Sheets API v4:
- Read spreadsheet metadata (sheets, title, grid properties)
- Read cell ranges (e.g. "Sheet1!A1:D20")
- Write cell ranges
- Append rows to a sheet
- Create new spreadsheet
- Add new sheets/tabs via batchUpdate
"""

from __future__ import annotations

from typing import Any

import structlog

from integrations.google.client import GoogleWorkspaceClient
from integrations.google.errors import GoogleInvalidArgumentError

logger = structlog.get_logger(__name__)

SHEETS_BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"


class SheetsService:
    """Service wrapper for Google Sheets API v4."""

    def __init__(self, client: GoogleWorkspaceClient | None = None) -> None:
        self.client = client or GoogleWorkspaceClient()

    async def get_spreadsheet(
        self, spreadsheet_id: str, include_grid_data: bool = False
    ) -> dict[str, Any]:
        """Fetch spreadsheet metadata including sheets and properties."""
        if not spreadsheet_id:
            raise GoogleInvalidArgumentError("spreadsheet_id is required.")
        url = f"{SHEETS_BASE_URL}/{spreadsheet_id}"
        params = {"includeGridData": str(include_grid_data).lower()}
        data = await self.client.request("GET", url, params=params)
        sheets_summary = [
            {
                "sheetId": s.get("properties", {}).get("sheetId"),
                "title": s.get("properties", {}).get("title"),
                "index": s.get("properties", {}).get("index"),
                "rowCount": s.get("properties", {}).get("gridProperties", {}).get("rowCount"),
                "columnCount": s.get("properties", {}).get("gridProperties", {}).get("columnCount"),
            }
            for s in data.get("sheets", [])
        ]
        return {
            "spreadsheetId": data.get("spreadsheetId"),
            "title": data.get("properties", {}).get("title"),
            "spreadsheetUrl": data.get("spreadsheetUrl"),
            "sheets": sheets_summary,
        }

    async def read_range(
        self,
        spreadsheet_id: str,
        range_notation: str,
        major_dimension: str = "ROWS",
        value_render_option: str = "FORMATTED_VALUE",
    ) -> dict[str, Any]:
        """
        Read values from a range (e.g. 'Sheet1!A1:D20' or 'A1:B10').
        Returns list of rows/columns.
        """
        if not spreadsheet_id or not range_notation:
            raise GoogleInvalidArgumentError("spreadsheet_id and range_notation are required.")

        url = f"{SHEETS_BASE_URL}/{spreadsheet_id}/values/{range_notation}"
        params = {
            "majorDimension": major_dimension,
            "valueRenderOption": value_render_option,
        }
        data = await self.client.request("GET", url, params=params)
        return {
            "spreadsheetId": spreadsheet_id,
            "range": data.get("range", range_notation),
            "majorDimension": data.get("majorDimension", major_dimension),
            "values": data.get("values", []),
        }

    async def write_range(
        self,
        spreadsheet_id: str,
        range_notation: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """
        Write or overwrite values in a specific range.
        value_input_option: 'USER_ENTERED' (parses formulas/numbers) or 'RAW'.
        """
        if not spreadsheet_id or not range_notation:
            raise GoogleInvalidArgumentError("spreadsheet_id and range_notation are required.")
        if values is None:
            raise GoogleInvalidArgumentError("values must be provided (list of rows).")

        url = f"{SHEETS_BASE_URL}/{spreadsheet_id}/values/{range_notation}"
        params = {"valueInputOption": value_input_option}
        body = {"range": range_notation, "values": values}

        data = await self.client.request("PUT", url, params=params, json_data=body)
        logger.info(
            "google_sheet_range_written",
            spreadsheet_id=spreadsheet_id,
            range=range_notation,
            updated_cells=data.get("updatedCells"),
        )
        return {
            "spreadsheetId": spreadsheet_id,
            "updatedRange": data.get("updatedRange"),
            "updatedRows": data.get("updatedRows"),
            "updatedColumns": data.get("updatedColumns"),
            "updatedCells": data.get("updatedCells"),
        }

    async def append_rows(
        self,
        spreadsheet_id: str,
        range_notation: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
        insert_data_option: str = "INSERT_ROWS",
    ) -> dict[str, Any]:
        """
        Append rows to a sheet below existing data in the specified range/sheet.
        """
        if not spreadsheet_id or not range_notation:
            raise GoogleInvalidArgumentError("spreadsheet_id and range_notation are required.")
        if not values:
            raise GoogleInvalidArgumentError("values list cannot be empty.")

        url = f"{SHEETS_BASE_URL}/{spreadsheet_id}/values/{range_notation}:append"
        params = {
            "valueInputOption": value_input_option,
            "insertDataOption": insert_data_option,
        }
        body = {"range": range_notation, "values": values}

        data = await self.client.request("POST", url, params=params, json_data=body)
        updates = data.get("updates", {})
        logger.info(
            "google_sheet_rows_appended",
            spreadsheet_id=spreadsheet_id,
            updated_cells=updates.get("updatedCells"),
        )
        return {
            "spreadsheetId": spreadsheet_id,
            "updatedRange": updates.get("updatedRange"),
            "updatedRows": updates.get("updatedRows"),
            "updatedColumns": updates.get("updatedColumns"),
            "updatedCells": updates.get("updatedCells"),
        }

    async def create_spreadsheet(
        self, title: str, sheet_titles: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a new Google Spreadsheet."""
        if not title or not title.strip():
            raise GoogleInvalidArgumentError("Spreadsheet title is required.")

        body: dict[str, Any] = {"properties": {"title": title.strip()}}
        if sheet_titles:
            body["sheets"] = [{"properties": {"title": st.strip()}} for st in sheet_titles if st.strip()]

        url = SHEETS_BASE_URL
        data = await self.client.request("POST", url, json_data=body)
        logger.info("google_spreadsheet_created", spreadsheet_id=data.get("spreadsheetId"), title=title)
        return {
            "spreadsheetId": data.get("spreadsheetId"),
            "title": data.get("properties", {}).get("title"),
            "spreadsheetUrl": data.get("spreadsheetUrl"),
        }

    async def add_sheet(self, spreadsheet_id: str, title: str) -> dict[str, Any]:
        """Add a new sheet/tab to an existing spreadsheet."""
        if not spreadsheet_id or not title:
            raise GoogleInvalidArgumentError("spreadsheet_id and sheet title are required.")

        request = {"addSheet": {"properties": {"title": title.strip()}}}
        url = f"{SHEETS_BASE_URL}/{spreadsheet_id}:batchUpdate"
        data = await self.client.request("POST", url, json_data={"requests": [request]})
        reply = data.get("replies", [{}])[0].get("addSheet", {}).get("properties", {})
        logger.info("google_sheet_tab_added", spreadsheet_id=spreadsheet_id, title=title)
        return {
            "spreadsheetId": spreadsheet_id,
            "sheetId": reply.get("sheetId"),
            "title": reply.get("title"),
        }
