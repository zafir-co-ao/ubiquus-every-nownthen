"""
Ubiquus MTB - Process negative stock quantities and create FT documents

This script retrieves products with negative quantities from Vendus API
and creates FT (Fatura) documents with due date 15 days from now.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

import requests


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================


def get_config():
    """Get configuration from environment variables."""
    return {
        "MTB_NIF": os.getenv("MTB_NIF", "5417196215"),
        "MTB_STORE_ID": os.getenv("MTB_STORE_ID", "217464989"),
        "MTB_VENDUS_API_KEY": os.getenv("MTB_VENDUS_API_KEY"),
        "VENDUS_API_KEY": os.getenv("VENDUS_API_KEY"),
        "MODE": os.getenv("MTB_MODE", "normal"),
    }


# =============================================================================
# VENDUS API OPERATIONS
# =============================================================================


def get_products_with_negative_qty(api_key: str, store_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves products with negative quantities from Vendus API.

    Args:
        api_key: MTB Vendus API key
        store_id: MTB Store ID

    Returns:
        List of products with negative quantities.
    """
    try:
        response = requests.get(
            "https://www.vendus.pt/ws/v1.1/products/",
            params={
                "api_key": api_key,
                "status": "on",
                "per_page": 500,
                "store_id": store_id,
            },
        )

        if response.status_code == 200:
            products = response.json()
            negative_qty_products = []

            for product in products:
                qty = product.get("stock", 0)
                if qty < 0:
                    reference = product.get("reference")
                    product = {"reference": reference, "qty": qty}
                    negative_qty_products.append(product)

            return negative_qty_products
        else:
            print(
                f"Failed to retrieve products. Status code: {response.status_code}, Response: {response.text}"
            )
            return []

    except Exception as e:
        print(f"Error retrieving products: {e}")
        return []


def create_sales_items_from_products(
    products: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Converts products with negative quantities to sales items format.

    Args:
        products: List of products with negative quantities.

    Returns:
        List of sales items for API payload.
    """
    items = []

    for product in products:
        item = {
            "reference": product.get("reference", ""),
            "qty": abs(product.get("qty", 0)),  # Convert negative to positive
        }
        items.append(item)

    return items


def create_ft_document_payload(
    sales_items: List[Dict[str, Any]],
    due_date: str,
    document_type: str,
    nif: str,
    mode: str,
) -> Dict[str, Any]:
    """
    Creates the payload for FT document API request.

    Args:
        sales_items: List of sales items.
        due_date: Due date for the document (YYYY-MM-DD format).
        document_type: Type of document (FT or PF)
        nif: Customer NIF
        mode: Mode for document creation

    Returns:
        API payload dictionary.
    """
    payload = {
        "type": document_type,
        "mode": mode,
        "date_due": due_date,
        "client": {"fiscal_id": nif},
        "items": sales_items,
    }

    return payload


def send_document(payload: Dict[str, Any], api_key: str) -> bool:
    """
    Sends FT document to Vendus API.

    Args:
        payload: Document payload.
        api_key: Ubiquus Vendus API key

    Returns:
        True if successful, False otherwise.
    """
    try:
        response = requests.post(
            "https://www.vendus.pt/ws/v1.1/documents/",
            params={"api_key": api_key},
            json=payload,
        )

        if response.status_code in [200, 201]:
            print("FT Document created successfully.")
            return True
        else:
            print(
                f"Failed to create document. Status code: {response.status_code}, Response: {response.text}"
            )
            return False

    except Exception as e:
        print(f"Error sending document: {e}")
        return False


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
# MAIN EXECUTION
# =============================================================================


def run(dry_run: bool = False, due_days: int = 15) -> bool:
    """
    Main execution function for process_mtb_sales.

    Args:
        dry_run: Whether to run in dry-run mode
        due_days: Number of days from now for due date

    Returns:
        True if successful, False otherwise
    """
    config = get_config()

    # Validate required environment variables
    if not config["MTB_VENDUS_API_KEY"]:
        print("Error: MTB_VENDUS_API_KEY environment variable is required")
        return False

    if not config["VENDUS_API_KEY"]:
        print("Error: VENDUS_API_KEY environment variable is required")
        return False

    # Calculate due date
    due_date = get_due_date(due_days)

    if dry_run:
        print("Running in DRY-RUN mode...")
    else:
        print("Running in PRODUCTION mode...")

    print(f"Due date set to: {due_date}")

    try:
        # Retrieve products with negative quantities
        print("Retrieving products with negative quantities...")
        negative_qty_products = get_products_with_negative_qty(
            config["MTB_VENDUS_API_KEY"], config["MTB_STORE_ID"]
        )

        if not negative_qty_products:
            print("No products with negative quantities found.")
            return True

        print(f"Found {len(negative_qty_products)} products with negative quantities:")
        for product in negative_qty_products:
            reference = product.get("reference", "N/A")
            qty = product.get("qty", 0)
            print(f"  - {reference}: {qty}")

        # Convert to sales items
        sales_items = create_sales_items_from_products(negative_qty_products)

        # Create FT document payload
        if dry_run:
            print("\nDRY-RUN: Creating PF document...")
            payload = create_ft_document_payload(
                sales_items, due_date, "PF", config["MTB_NIF"], config["MODE"]
            )
        else:
            print("\nCreating FT document...")
            payload = create_ft_document_payload(
                sales_items, due_date, "FT", config["MTB_NIF"], config["MODE"]
            )

        print(f"Customer Fiscal ID: {config['MTB_NIF']}")
        print(f"Due Date: {due_date}")
        print(f"Items Count: {len(sales_items)}")

        success = send_document(payload, config["VENDUS_API_KEY"])

        if success:
            print(f"Successfully processed {len(sales_items)} items.")

        return success

    except Exception as e:
        print(f"Error during execution: {e}")
        return False
