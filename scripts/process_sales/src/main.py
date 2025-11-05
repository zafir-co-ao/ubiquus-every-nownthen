"""
Main executable for monthly sales processing.

This script orchestrates the execution of three sales processors:
1. process_sales - Processes sales for all clients except excluded NIFs
2. process_seven_sales - Processes sales for Seven Gym
3. process_mtb_sales - Processes MTB negative stock quantities
"""

import argparse
import sys
from datetime import date
from calendar import monthrange

from . import process_sales
from . import process_seven_sales
from . import process_mtb_sales


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


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process monthly sales for all clients and generate invoices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables Required:
  SERVICE_ACCOUNT_KEY_PATH    Path to Google service account key file
  VENDUS_API_KEY              Vendus API key for general sales and MTB documents
  MTB_VENDUS_API_KEY          Vendus API key for Seven and MTB sales

  # Optional - Common
  ROOT_FOLDER                 Google Drive root folder ID (default: 1yStonR5SunFaBUPBCIw8WBzaw_dRWxph)

  # Optional - Ubiquus Sales (process_sales)
  UBIQUUS_EXCLUDED_NIFS       Comma-separated list of NIFs to exclude (default: 5480033140,5417196215)
  UBIQUUS_MODE                Processing mode (default: normal)

  # Optional - Seven Sales (process_seven_sales)
  SEVEN_REGISTER_ID           Seven register ID (default: 217465187)
  SEVEN_PAYMENT_ID            Seven payment ID (default: 85469894)
  SEVEN_NIF                   Seven NIF (default: 5480033140)
  SEVEN_MODE                  Processing mode (default: normal)

  # Optional - MTB Sales (process_mtb_sales)
  MTB_STORE_ID                MTB store ID (default: 217464989)
  MTB_NIF                     MTB NIF (default: 5417196215)
  MTB_MODE                    Processing mode (default: normal)

Examples:
  # Process last month's sales in production mode
  process_monthly_sales

  # Process specific date range in dry-run mode
  process_monthly_sales 2024-01-01 2024-01-31 --dry-run

  # Process last month in dry-run mode
  process_monthly_sales --dry-run
        """,
    )

    parser.add_argument(
        "start_date",
        nargs="?",
        default=None,
        help="Start date for filtering (YYYY-MM-DD format). Defaults to first day of last month if not provided.",
    )
    parser.add_argument(
        "end_date",
        nargs="?",
        default=None,
        help="End date for filtering (YYYY-MM-DD format). Defaults to last day of last month if not provided.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (creates PF/Proforma documents instead of production documents)",
    )

    args = parser.parse_args()

    # Handle date arguments logic
    if args.start_date and not args.end_date:
        print("Error: If start_date is provided, end_date must also be provided")
        sys.exit(1)

    # Set default dates if neither is provided
    if not args.start_date and not args.end_date:
        default_start, default_end = get_last_month_dates()
        args.start_date = default_start
        args.end_date = default_end
        print(f"No dates provided, using last month: {default_start} to {default_end}")

    return args


def main():
    """Main execution function."""
    args = parse_arguments()

    print("=" * 80)
    print("UBIQUUS MONTHLY SALES PROCESSOR")
    print("=" * 80)
    print(f"Date Range: {args.start_date} to {args.end_date}")
    print(
        f"Mode: {'DRY-RUN (Proforma/PF documents)' if args.dry_run else 'PRODUCTION (FT/FR documents)'}"
    )
    print("=" * 80)
    print()

    # Track overall success
    all_success = True
    results = []

    # 1. Process general sales (all clients except excluded NIFs)
    print("STEP 1/3: Processing general sales (excluding specific NIFs)")
    print("-" * 80)
    try:
        success = process_sales.run(
            start_date=args.start_date, end_date=args.end_date, dry_run=args.dry_run
        )
        results.append(("General Sales", success))
        if not success:
            all_success = False
            print("WARNING: General sales processing failed")
        print()
    except Exception as e:
        print(f"ERROR: General sales processing failed with exception: {e}")
        results.append(("General Sales", False))
        all_success = False
        print()

    # 2. Process Seven sales
    print("STEP 2/3: Processing Seven Gym sales")
    print("-" * 80)
    try:
        success = process_seven_sales.run(
            start_date=args.start_date, end_date=args.end_date, dry_run=args.dry_run
        )
        results.append(("Seven Sales", success))
        if not success:
            all_success = False
            print("WARNING: Seven sales processing failed")
        print()
    except Exception as e:
        print(f"ERROR: Seven sales processing failed with exception: {e}")
        results.append(("Seven Sales", False))
        all_success = False
        print()

    # 3. Process MTB sales
    print("STEP 3/3: Processing MTB negative stock")
    print("-" * 80)
    try:
        success = process_mtb_sales.run(dry_run=args.dry_run, due_days=15)
        results.append(("MTB Sales", success))
        if not success:
            all_success = False
            print("WARNING: MTB sales processing failed")
        print()
    except Exception as e:
        print(f"ERROR: MTB sales processing failed with exception: {e}")
        results.append(("MTB Sales", False))
        all_success = False
        print()

    # Print summary
    print("=" * 80)
    print("PROCESSING SUMMARY")
    print("=" * 80)
    for process_name, success in results:
        status = "SUCCESS" if success else "FAILED"
        symbol = "✓" if success else "✗"
        print(f"{symbol} {process_name}: {status}")
    print("=" * 80)

    if all_success:
        print("\nAll sales processing completed successfully!")
        sys.exit(0)
    else:
        print("\nSome sales processing steps failed. Please review the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
