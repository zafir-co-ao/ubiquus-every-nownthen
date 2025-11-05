"""
Ubiquus Seven - Google Drive CSV processor and Vendus invoice generator

This script downloads CSV files from Google Drive, processes sales data,
and creates invoices using the Vendus API.
"""

import os
import tempfile
from datetime import date
from calendar import monthrange
from typing import List, Dict, Any, Optional

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
        "VENDUS_API_KEY": os.getenv("MTB_VENDUS_API_KEY"),
        "REGISTER_ID": os.getenv("SEVEN_REGISTER_ID", "217465187"),
        "PAYMENT_ID": os.getenv("SEVEN_PAYMENT_ID", "85469894"),
        "NIF": os.getenv("SEVEN_NIF", "5480033140"),
        "MODE": os.getenv("SEVEN_MODE", "normal"),
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


def filter_files(
    files: List[Dict[str, str]], nif: str, start_date: str, end_date: str
) -> List[Dict[str, str]]:
    """
    Filters files based on NIF and date range.

    Args:
        files: List of file metadata dictionaries.
        nif: NIF to filter by.
        start_date: Start date for filtering (inclusive).
        end_date: End date for filtering (inclusive).

    Returns:
        A list of filtered file metadata dictionaries.
    """
    filtered_files = []

    for file in files:
        filename = file["name"]
        if nif in filename:
            created_time = filename[:10]
            if start_date <= created_time <= end_date:
                filtered_files.append(file)

    return filtered_files


def download_files(service, files: List[Dict[str, str]]) -> List[str]:
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

    return downloaded_files


# =============================================================================
# DATA PROCESSING
# =============================================================================


def process_csv_files(files: List[str]) -> pd.DataFrame:
    """
    Processes CSV files and returns consolidated DataFrame.

    Args:
        files: List of file paths to process.

    Returns:
        Consolidated and processed DataFrame.
    """
    dfs = []

    for file in files:
        df = pd.read_csv(
            file,
            encoding="utf-8",
            sep=",",
            skip_blank_lines=True,
            skiprows=10,
            skipfooter=1,
            engine="python",
        )
        dfs.append(df)

    # Consolidate all dataframes
    df = pd.concat(dfs, ignore_index=True)

    # Process and clean data
    df = df[["CÓDIGO", "REP."]]
    df = df.rename(columns={"CÓDIGO": "codigo", "REP.": "reposicao"})  # type: ignore
    df = df[df["reposicao"] > 0]
    df = df.groupby("codigo", as_index=False).sum()

    return df  # type: ignore


def create_sales_items(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Converts DataFrame to sales items format for API.

    Args:
        df: Processed DataFrame with sales data.

    Returns:
        List of sales items for API payload.
    """
    items = []

    for _, row in df.iterrows():
        item = {"reference": row["codigo"], "qty": row["reposicao"]}
        items.append(item)

    return items


# =============================================================================
# INVOICE OPERATIONS
# =============================================================================


def create_invoice_payload(
    sales: List[Dict[str, Any]],
    document_type: str,
    register_id: str,
    mode: str,
    payment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates the payload for invoice API request.

    Args:
        sales: List of sales items.
        document_type: Type of document ("PF" or "FR").
        register_id: Register ID
        mode: Mode for document creation
        payment_id: Payment ID (optional).

    Returns:
        API payload dictionary.
    """
    payload = {
        "register_id": register_id,
        "type": document_type,
        "mode": mode,
        "external_reference": "Seven Gym",
        "items": sales,
    }

    if payment_id:
        payload["payments"] = [{"id": payment_id}]

    return payload


def send_invoice(payload: Dict[str, Any], api_key: str) -> bool:
    """
    Sends invoice to Vendus API.

    Args:
        payload: Invoice payload.
        api_key: Vendus API key

    Returns:
        True if successful, False otherwise.
    """
    try:
        response = requests.post(
            f"https://www.vendus.pt/ws/v1.1/documents/?api_key={api_key}", json=payload
        )

        if response.status_code in [200, 201]:
            print("Document created successfully.")
            return True
        else:
            print(
                f"Failed to create document. Status code: {response.status_code}, Response: {response.text}"
            )
            return False

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
    Main execution function for process_seven_sales.

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
        print("Error: MTB_VENDUS_API_KEY environment variable is required")
        return False

    # Set default dates if not provided
    if not start_date and not end_date:
        start_date, end_date = get_last_month_dates()
        print(f"No dates provided, using last month: {start_date} to {end_date}")

    # Determine document configuration based on dry-run flag
    if dry_run:
        document_type = "PF"
        payment_id = None
        print("Running in DRY-RUN mode...")
    else:
        document_type = "FR"
        payment_id = config["PAYMENT_ID"]
        print("Running in PRODUCTION mode...")

    try:
        # Initialize Google Drive service
        print("Connecting to Google Drive...")
        service = create_drive_service(config["SERVICE_ACCOUNT_KEY_PATH"])

        # List and filter files
        print(f"Listing files for date range: {start_date} to {end_date}")
        files = list_files(service, config["ROOT_FOLDER"])
        filtered_files = filter_files(files, config["NIF"], start_date, end_date)

        if not filtered_files:
            print("No files found matching the criteria.")
            return True

        print(f"Found {len(filtered_files)} matching files.")

        # Download files
        print("Downloading files...")
        downloaded_files = download_files(service, filtered_files)

        # Process data
        print("Processing sales data...")
        df = process_csv_files(downloaded_files)
        sales_items = create_sales_items(df)

        if not sales_items:
            print("No sales data found to process.")
            return True

        print(f"Processed {len(sales_items)} sales items.")

        # Create and send invoice
        payload = create_invoice_payload(
            sales_items,
            document_type,
            config["REGISTER_ID"],
            config["MODE"],
            payment_id,
        )

        if dry_run:
            print("DRY-RUN: Creating Proforma invoice...")
        else:
            print("Creating invoice...")

        print(f"Items Count: {len(sales_items)}")
        success = send_invoice(payload, config["VENDUS_API_KEY"])
        return success

    except Exception as e:
        print(f"Error during execution: {e}")
        return False
