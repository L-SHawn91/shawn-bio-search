"""Download subpackage: OA-only PDF and dataset file collection.

Pipeline: plan (resolve URLs, write manifest) -> execute (fetch files).
Paywall bypass is explicitly NOT supported.
"""

from .manifest import load_manifest, save_manifest, merge_entry, new_manifest
from .resolver import resolve_pdf_url
from .dataset_resolver import enumerate_dataset_files
from .fetcher import download_to_path
from .runner import plan_from_bundle, execute_manifest, plan_and_execute, main_cli

__all__ = [
    "load_manifest",
    "save_manifest",
    "merge_entry",
    "new_manifest",
    "resolve_pdf_url",
    "enumerate_dataset_files",
    "download_to_path",
    "plan_from_bundle",
    "execute_manifest",
    "plan_and_execute",
    "main_cli",
]
