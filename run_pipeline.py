#!/usr/bin/env python3

"""
Olist E-Commerce Data Preparation & Source-System Simulator
Pipeline Orchestrator

This script orchestrates the complete data preparation pipeline:

1. Transform source datasets
2. Validate cross-table integrity
3. Load transformed datasets into PostgreSQL
4. Run database-level integrity audit

The pipeline stops immediately if any critical stage fails.
Known source-data anomalies that are intentionally preserved are
handled by the individual validation/load scripts.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

# PROJECT CONFIGURATION

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

TRANSFORM_DIR = SRC_DIR / "transform"
LOAD_DIR = SRC_DIR / "load"
VALIDATION_DIR = SRC_DIR / "validation"

PYTHON_EXECUTABLE = sys.executable


# LOGGING CONFIGURATION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("pipeline")


# PIPELINE COMMANDS

# IMPORTANT:
# Keep this order deliberate. Some datasets depend on others.

TRANSFORM_SCRIPTS = [
    # Customer/source entities
    "transform_customers.py",

    # Product/seller entities
    "transform_products.py",
    "transform_sellers.py",

    # Financial/customer-interaction entities
    "transform_payments.py",
    "transform_reviews.py",

    # Transactional entities
    "transform_orders.py",
    "transform_order_items.py",

    # Geographic & Enrichment reference data
    "transform_geolocation.py",
    "enrich_customer_signup_date.py",
]


LOAD_SCRIPTS = [
    # Reference/lookup data first
    "load_geolocation.py",

    # Product and seller reference entities
    "load_products.py",
    "load_sellers.py",

    # Core customer and transactional entities
    "load_customers.py",
    "load_orders.py",

    # Dependent transaction entities
    "load_payments.py",
    "load_reviews.py",
    "load_order_items.py",
]


VALIDATION_SCRIPTS = [
    # Source-level cross-table validation
    "validate_cross_table_integrity.py",

    # Final PostgreSQL database-level validation
    "audit_database_integrity.py",
]

# UTILITY FUNCTIONS

def print_banner(title: str) -> None:
    """Print a formatted pipeline section banner."""

    logger.info("=" * 70)
    logger.info(title)
    logger.info("=" * 70)


def run_script(
    script_path: Path,
    stage_name: str,
) -> None:
    """
    Execute a Python script and stop the pipeline if it fails.
    """

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required script not found: {script_path}"
        )

    logger.info("Starting %s", script_path.name)
    logger.info("Script: %s", script_path)

    start_time = time.perf_counter()

    result = subprocess.run(
        [PYTHON_EXECUTABLE, str(script_path)],
        cwd=PROJECT_ROOT,
    )

    elapsed = time.perf_counter() - start_time

    if result.returncode != 0:
        logger.error(
            "%s FAILED: %s returned exit code %s",
            stage_name,
            script_path.name,
            result.returncode,
        )

        raise RuntimeError(
            f"{stage_name} failed: {script_path.name}"
        )

    logger.info(
        "%s completed successfully: %s (%.2f seconds)",
        stage_name,
        script_path.name,
        elapsed,
    )


def run_stage(
    stage_name: str,
    scripts: list[str],
    directory: Path,
) -> None:
    """
    Execute all scripts belonging to a pipeline stage.
    """

    print_banner(f"STARTING STAGE: {stage_name}")

    stage_start = time.perf_counter()

    for script_name in scripts:
        script_path = directory / script_name

        run_script(
            script_path=script_path,
            stage_name=stage_name,
        )

    elapsed = time.perf_counter() - stage_start

    logger.info("=" * 70)
    logger.info(
        "STAGE COMPLETED: %s | %.2f seconds",
        stage_name,
        elapsed,
    )
    logger.info("=" * 70)


# MAIN PIPELINE

def main() -> int:

    pipeline_start = time.perf_counter()

    print_banner(
        "OLIST E-COMMERCE DATA PREPARATION PIPELINE STARTING"
    )

    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Python executable: %s", PYTHON_EXECUTABLE)

    try:

        # STAGE 1 — TRANSFORMATION

        run_stage(
            stage_name="DATA TRANSFORMATION",
            scripts=TRANSFORM_SCRIPTS,
            directory=TRANSFORM_DIR,
        )

        # STAGE 2 — SOURCE-LEVEL VALIDATION

        run_stage(
            stage_name="SOURCE DATA VALIDATION",
            scripts=VALIDATION_SCRIPTS[:1],
            directory=VALIDATION_DIR,
        )

        # STAGE 3 — DATABASE LOAD

        run_stage(
            stage_name="POSTGRESQL DATA LOAD",
            scripts=LOAD_SCRIPTS,
            directory=LOAD_DIR,
        )

        # STAGE 4 — DATABASE-LEVEL AUDIT

        run_stage(
            stage_name="DATABASE INTEGRITY AUDIT",
            scripts=VALIDATION_SCRIPTS[1:],
            directory=VALIDATION_DIR,
        )

        # PIPELINE SUCCESS

        elapsed = time.perf_counter() - pipeline_start

        print_banner(
            "OLIST E-COMMERCE DATA PREPARATION PIPELINE COMPLETED SUCCESSFULLY"
        )

        logger.info(
            "Total pipeline execution time: %.2f seconds",
            elapsed,
        )

        logger.info(
            "All transformations completed successfully."
        )

        logger.info(
            "All source-level validations completed successfully."
        )

        logger.info(
            "All PostgreSQL loads completed successfully."
        )

        logger.info(
            "Database-level integrity audit completed successfully."
        )

        return 0

    except KeyboardInterrupt:

        logger.error(
            "Pipeline interrupted by user."
        )

        return 130

    except Exception as exc:

        elapsed = time.perf_counter() - pipeline_start

        logger.error("=" * 70)
        logger.error(
            "OLIST PIPELINE FAILED."
        )
        logger.error(
            "Failure: %s",
            exc,
        )
        logger.error(
            "Elapsed time before failure: %.2f seconds",
            elapsed,
        )
        logger.error(
            "Downstream processing should NOT proceed."
        )
        logger.error("=" * 70)

        return 1


if __name__ == "__main__":
    sys.exit(main())