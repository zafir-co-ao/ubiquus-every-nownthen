"""
Ubiquus Sales - Google Drive CSV processor and Vendus invoice generator for all clients except specified NIF

This script downloads CSV files from Google Drive, processes sales data for all clients
EXCEPT the specified NIF, and creates invoices using the Vendus API.
"""

import argparse
import os
import sys
import tempfile
from datetime import datetime, timedelta, date
from calendar import monthrange
from typing import List, Dict, Any, Tuple

import pandas as pd
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================


def get_config():
    """Get configuration from environment variables."""
    return {
        "SERVICE_ACCOUNT_KEY_PATH": os.getenv("SERVICE_ACCOUNT_KEY_PATH"),
        "ROOT_FOLDER": os.getenv("ROOT_FOLDER", "1yStonR5SunFaBUPBCIw8WBzaw_dRWxph"),
        "VENDUS_API_KEY": os.getenv("VENDUS_API_KEY"),
        "EXCLUDED_NIFS": os.getenv(
            "UBIQUUS_EXCLUDED_NIFS", "5480033140,5417196215"
        ).split(","),
        "MODE": os.getenv("UBIQUUS_MODE", "normal"),
    }


DRIVE_API_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


# =============================================================================
# GOOGLE DRIVE OPERATIONS
# =============================================================================


def create_drive_service(service_account_key_path: str):
    """
    Creates and returns an authenticated Google Drive API service object.

    Args:
        service_account_key_path: Path to the service account key file

    Returns:
        service: The authenticated Google Drive API service object
    """
    creds = Credentials.from_service_account_file(
        service_account_key_path, scopes=DRIVE_API_SCOPES
    )
    return build("drive", "v3", credentials=creds)


def list_files(service, folder_id: str) -> List[Dict[str, str]]:
    """
    Lists CSV files in a specified Google Drive folder.

    Args:
        service: The authenticated Google Drive API service object.
        folder_id: The ID of the folder to list files from.

    Returns:
        A list of file metadata dictionaries.
    """
    query = f"'{folder_id}' in parents and mimeType = 'text/csv' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])


def filter_files_exclude_nifs(
    files: List[Dict[str, str]],
    excluded_nifs: List[str],
    start_date: str,
    end_date: str,
) -> List[Dict[str, str]]:
    """
    Filters files excluding the specified NIF and within date range.

    Args:
        files: List of file metadata dictionaries.
        excluded_nifs: NIFS to exclude from processing.
        start_date: Start date for filtering (inclusive).
        end_date: End date for filtering (inclusive).

    Returns:
        A list of filtered file metadata dictionaries.
    """
    filtered_files = []

    for file in files:
        filename = file["name"]
        # Exclude files that contain any of the specified NIFs
        if not any(nif in filename for nif in excluded_nifs):
            created_time = filename[:10]
            if start_date <= created_time <= end_date:
                filtered_files.append(file)

    return filtered_files


def download_files(service, files: List[Dict[str, str]]) -> Tuple[List[str], List[str]]:
    """
    Downloads files from Google Drive to temporary directory.

    Args:
        service: The authenticated Google Drive API service object.
        files: A list of file metadata dictionaries to download.

    Returns:
        A list of paths to the downloaded files.
    """
    tmp_dir = tempfile.gettempdir()
    downloaded_files = []
    filenames = []

    for file in files:
        file_id = file["id"]
        request = service.files().get_media(fileId=file_id)
        file_name = f"{tmp_dir}/{file['name']}"

        with open(file_name, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        downloaded_files.append(file_name)
        filenames.append(file["name"])

    return downloaded_files, filenames


# =============================================================================
# DATA PROCESSING
# =============================================================================


def process_csv_files(files: List[str], filenames: List[str]) -> pd.DataFrame:
    """
    Processes CSV files and returns consolidated DataFrame.

    Args:
        files: List of file paths to process.
        filenames: List of filenames corresponding to the files.

    Returns:
        Consolidated and processed DataFrame.
    """
    dfs = []

    for file, filename in zip(files, filenames):
        df = pd.read_csv(
            file,
            encoding="utf-8",
            sep=",",
            skip_blank_lines=True,
            skiprows=10,
            skipfooter=1,
            engine="python",
        )

        df["nif"] = filename[11:-4]

        dfs.append(df)

    # Consolidate all dataframes
    df = pd.concat(dfs, ignore_index=True)

    # Process and clean data
    df = df[["CÓDIGO", "REP.", "nif"]]
    df = df.rename(columns={"CÓDIGO": "codigo", "REP.": "reposicao"})  # type: ignore
    df = df[df["reposicao"] > 0]

    return df  # type: ignore


def create_sales_items(df: pd.DataFrame) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    Converts DataFrame to sales items format for API.

    Args:
        df: Processed DataFrame with sales data.

    Returns:
        List of sales items for API payload.
    """

    # Get uniques NIFS
    nifs = df["nif"].unique()

    sales_items = []

    for nif in nifs:
        client_df = df[df["nif"] == nif]
        client_df = client_df.groupby("codigo", as_index=False).sum()

        items = []
        for _, row in client_df.iterrows():
            item = {"reference": row["codigo"], "qty": row["reposicao"]}

            items.append(item)
        sales_items.append((nif, items))

    return sales_items


# =============================================================================
# DATE UTILITIES
# =============================================================================


def get_due_date(days_from_now: int = 15) -> str:
    """
    Calculate due date N days from now.

    Args:
        days_from_now: Number of days from today (default: 15).

    Returns:
        Due date in YYYY-MM-DD format.
    """
    due_date = datetime.now() + timedelta(days=days_from_now)
    return due_date.strftime("%Y-%m-%d")


# =============================================================================
# INVOICE OPERATIONS
# =============================================================================


def create_invoices_payloads(
    sales: List[Tuple[str, List[Dict[str, Any]]]], document_type: str, mode: str
) -> List[Dict[str, Any]]:
    """
    Creates the payload for invoice API request.

    Args:
        sales: List of sales items.
        document_type: Type of document ("PF" or "FR").
        mode: Mode for document creation

    Returns:
        API payload dictionary.
    """
    payloads = []
    for client_sales in sales:
        payload = {
            "client": {"fiscal_id": client_sales[0]},
            "type": document_type,
            "date_due": get_due_date(),
            "mode": mode,
            "items": client_sales[1],
        }

        payloads.append(payload)
    return payloads


def send_invoices(payloads: List[Dict[str, Any]], api_key: str) -> bool:
    """
    Sends invoice to Vendus API.

    Args:
        payloads: List of invoice payloads.
        api_key: Vendus API key

    Returns:
        True if successful, False otherwise.
    """
    try:
        for payload in payloads:
            response = requests.post(
                "https://www.vendus.pt/ws/v1.1/documents/",
                params={"api_key": api_key},
                json=payload,
            )

            if response.status_code in [200, 201]:
                print(
                    f"Document created successfully. NIF: {payload['client']['fiscal_id']}"
                )
            else:
                print(
                    f"Failed to create document. Status code: {response.status_code}, Response: {response.text}"
                )
                return False
        return True

    except Exception as e:
        print(f"Error sending invoice: {e}")
        return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================


def get_last_month_dates():
    """
    Get the first and last day of the previous month.

    Returns:
        tuple: (start_date, end_date) as strings in YYYY-MM-DD format
    """
    today = date.today()

    # Calculate last month
    if today.month == 1:
        last_month = 12
        last_year = today.year - 1
    else:
        last_month = today.month - 1
        last_year = today.year

    # First day of last month
    start_date = date(last_year, last_month, 1)

    # Last day of last month
    _, last_day = monthrange(last_year, last_month)
    end_date = date(last_year, last_month, last_day)

    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def run(start_date: str = None, end_date: str = None, dry_run: bool = False) -> bool:
    """
    Main execution function for process_sales.

    Args:
        start_date: Start date for filtering (YYYY-MM-DD format)
        end_date: End date for filtering (YYYY-MM-DD format)
        dry_run: Whether to run in dry-run mode

    Returns:
        True if successful, False otherwise
    """
    config = get_config()

    # Validate required environment variables
    if not config["SERVICE_ACCOUNT_KEY_PATH"]:
        print("Error: SERVICE_ACCOUNT_KEY_PATH environment variable is required")
        return False

    if not config["VENDUS_API_KEY"]:
        print("Error: VENDUS_API_KEY environment variable is required")
        return False

    # Set default dates if not provided
    if not start_date and not end_date:
        start_date, end_date = get_last_month_dates()
        print(f"No dates provided, using last month: {start_date} to {end_date}")

    # Determine document configuration based on dry-run flag
    if dry_run:
        document_type = "PF"
        print("Running in DRY-RUN mode...")
    else:
        document_type = "FT"
        print("Running in PRODUCTION mode...")

    print(f"Excluding NIFS: {config['EXCLUDED_NIFS']}")

    try:
        # Initialize Google Drive service
        print("Connecting to Google Drive...")
        service = create_drive_service(config["SERVICE_ACCOUNT_KEY_PATH"])

        # List and filter files (excluding specified NIF)
        print(f"Listing files for date range: {start_date} to {end_date}")
        files = list_files(service, config["ROOT_FOLDER"])
        filtered_files = filter_files_exclude_nifs(
            files, config["EXCLUDED_NIFS"], start_date, end_date
        )

        if not filtered_files:
            print("No files found matching the criteria.")
            return True

        print(f"Found {len(filtered_files)} matching files.")

        # Download files
        print("Downloading files...")
        downloaded_files, filenames = download_files(service, filtered_files)

        # Process data
        print("Processing sales data...")
        df = process_csv_files(downloaded_files, filenames)
        sales_items = create_sales_items(df)

        if not sales_items:
            print("No sales data found to process.")
            return True

        print(f"Processed {len(sales_items)} sales items.")

        # Create and send invoice
        payloads = create_invoices_payloads(sales_items, document_type, config["MODE"])

        if dry_run:
            print("DRY-RUN: Creating Proforma invoice...")
        else:
            print("Creating invoice...")

        print(f"Items Count: {len(sales_items)}")
        success = send_invoices(payloads, config["VENDUS_API_KEY"])
        return success

    except Exception as e:
        print(f"Error during execution: {e}")
        return False
