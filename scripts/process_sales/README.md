# Ubiquus Sales Processor

Monthly sales processor for Ubiquus invoicing system. This tool processes sales data from Google Drive and creates invoices using the Vendus API.

## Installation

This package uses `uv` for package management. Install it using:

```bash
# From the scripts/process_sales directory
uv tool install .
```

Or install directly from the repository:

```bash
uv tool install git+https://github.com/zafir-co-ao/ubiquus-every-nownthen.git#subdirectory=scripts/process_sales
```

## Usage

The main executable is `process-monthly-sales`, which orchestrates three sales processors:

1. **General Sales** - Processes sales for all clients except excluded NIFs
2. **Seven Sales** - Processes sales for Seven Gym
3. **MTB Sales** - Processes MTB negative stock quantities

### Basic Usage

```bash
# Process last month's sales in production mode
process-monthly-sales

# Process specific date range in dry-run mode
process-monthly-sales 2024-01-01 2024-01-31 --dry-run

# Process last month in dry-run mode
process-monthly-sales --dry-run
```

### Command Line Options

- `start_date` (optional): Start date for filtering (YYYY-MM-DD format). Defaults to first day of last month.
- `end_date` (optional): End date for filtering (YYYY-MM-DD format). Defaults to last day of last month.
- `--dry-run`: Run in dry-run mode (creates PF/Proforma documents instead of production FT/FR documents)

## Environment Variables

All configuration is done through environment variables. The following variables are required:

### Required Configuration

```bash
# Path to Google service account key file
export SERVICE_ACCOUNT_KEY_PATH="/path/to/service-account-key.json"

# Vendus API keys
export VENDUS_API_KEY="your-vendus-api-key"  # For general sales and MTB documents
export MTB_VENDUS_API_KEY="your-mtb-vendus-api-key"  # For Seven and MTB sales
```

### Optional Configuration (defaults provided)

```bash
# Common
export ROOT_FOLDER="1yStonR5SunFaBUPBCIw8WBzaw_dRWxph"

# Ubiquus Sales (process_sales)
export UBIQUUS_EXCLUDED_NIFS="5480033140,5417196215"  # Comma-separated
export UBIQUUS_MODE="normal"

# Seven Sales (process_seven_sales)
export SEVEN_REGISTER_ID="217465187"
export SEVEN_PAYMENT_ID="85469894"
export SEVEN_NIF="5480033140"
export SEVEN_MODE="normal"

# MTB Sales (process_mtb_sales)
export MTB_STORE_ID="217464989"
export MTB_NIF="5417196215"
export MTB_MODE="normal"
```

## Example Configuration Script

Create a `.env` file or configuration script:

```bash
#!/bin/bash
# sales_env.sh

# Required
export SERVICE_ACCOUNT_KEY_PATH="/tmp/everynownthen-39be8703e9c0.json"
export VENDUS_API_KEY="c016505bf6d1ef93c37238b23532d4ee"
export MTB_VENDUS_API_KEY="5a02b9c3da076f84e7f139639a8c8c42"
```

Then source it before running:

```bash
source sales_env.sh
process-monthly-sales
```

## Development

### Local Development Setup

```bash
# Navigate to the package directory
cd scripts/process_sales

# Install in editable mode with uv
uv pip install -e .

# Or run directly without installation
uv run python -m ubiquus_sales_processor.main
```

### Running Individual Processors

You can also import and run individual processors programmatically:

```python
from ubiquus_sales_processor import process_sales, process_seven_sales, process_mtb_sales

# Run general sales processor
success = process_sales.run(
    start_date="2024-01-01",
    end_date="2024-01-31",
    dry_run=True
)

# Run Seven sales processor
success = process_seven_sales.run(
    start_date="2024-01-01",
    end_date="2024-01-31",
    dry_run=True
)

# Run MTB sales processor
success = process_mtb_sales.run(
    dry_run=True,
    due_days=15
)
```

## How It Works

### General Sales (process_sales)

1. Connects to Google Drive using service account credentials
2. Lists and filters CSV files from the specified folder, excluding files for specified NIFs
3. Downloads matching CSV files to a temporary directory
4. Processes the CSV files to extract sales data
5. Creates invoice payloads for each client
6. Submits invoices to Vendus API

### Seven Sales (process_seven_sales)

1. Connects to Google Drive using service account credentials
2. Lists and filters CSV files for the Seven NIF
3. Downloads matching CSV files
4. Processes and consolidates sales data
5. Creates a single invoice for Seven Gym
6. Submits invoice to Vendus API

### MTB Sales (process_mtb_sales)

1. Queries Vendus API for products with negative stock quantities in the MTB store
2. Converts negative quantities to positive sales items
3. Creates an FT (Fatura) document for MTB with a 15-day due date
4. Submits document to Vendus API

## Dry-Run Mode

When using `--dry-run`:

- General Sales creates **PF** (Proforma) documents instead of **FT** (Fatura)
- Seven Sales creates **PF** (Proforma) documents instead of **FR** (Fatura-Recibo) and excludes payment information
- MTB Sales creates **PF** (Proforma) documents instead of **FT** (Fatura)

This allows you to test the entire pipeline without creating official invoices.

## Troubleshooting

### Missing Environment Variables

If you see errors about missing environment variables, ensure all required variables are set. Use the example configuration script above as a template.

### Google Drive Authentication Issues

Ensure the `SERVICE_ACCOUNT_KEY_PATH` points to a valid service account key file with access to the Google Drive folder.

### API Errors

Check that all API keys are valid and have the necessary permissions in Vendus.

## License

Internal use only - Zafir Co. AO
