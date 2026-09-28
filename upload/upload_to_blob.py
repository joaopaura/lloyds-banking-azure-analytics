#!/usr/bin/env python3
"""
Lloyds portfolio | Upload generated Parquet files to Azure Data Lake (Blob) - landing zone
===========================================================================================
Uploads every file under ../data to the container 'landing', keeping the same folder
structure (source/table/year=YYYY/month=MM/file.parquet). Files already uploaded with the
same size are skipped, so the script can be re-run safely (idempotent).

Security: the connection string is read from an environment variable, never stored in code.

PowerShell (VS Code terminal):
    $env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
    python upload\\upload_to_blob.py

Options:
    --container landing      target container (default: landing)
    --data ..\\data           local folder (default: ../data next to this script)
    --workers 8              parallel uploads
    --dry-run                list what would be uploaded, upload nothing
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings


def main():
    ap = argparse.ArgumentParser(description="Upload Lloyds synthetic data to Azure Blob / ADLS Gen2")
    ap.add_argument("--container", default="landing")
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        sys.exit("ERROR: set the environment variable AZURE_STORAGE_CONNECTION_STRING first (see header of this file).")
    root = Path(a.data)
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in (".parquet", ".json"))
    if not files:
        sys.exit(f"ERROR: no files found in {root}. Run the generator first.")

    svc = BlobServiceClient.from_connection_string(conn, max_single_put_size=8 * 1024 * 1024,
                                                   max_block_size=8 * 1024 * 1024)
    cont = svc.get_container_client(a.container)
    try:
        cont.create_container()
        print(f"container '{a.container}' created")
    except ResourceExistsError:
        pass

    print(f"Listing existing blobs in '{a.container}'...")
    existing = {b.name: b.size for b in cont.list_blobs()}
    todo = []
    for p in files:
        name = p.relative_to(root).as_posix()
        if existing.get(name) == p.stat().st_size:
            continue
        todo.append((p, name))
    total_mb = sum(p.stat().st_size for p, _ in todo) / 1e6
    print(f"{len(files):,} local files | {len(files) - len(todo):,} already uploaded | "
          f"{len(todo):,} to upload ({total_mb:,.0f} MB)")
    if a.dry_run or not todo:
        for p, name in todo[:20]:
            print("  would upload:", name)
        print("Nothing uploaded." if a.dry_run else "Everything is already uploaded.")
        return

    def upload(item):
        p, name = item
        ctype = "application/json" if p.suffix == ".json" else "application/octet-stream"
        with open(p, "rb") as fh:
            cont.upload_blob(name, fh, overwrite=True, max_concurrency=2,
                             content_settings=ContentSettings(content_type=ctype))
        return p.stat().st_size

    t0 = time.time(); done = 0; done_mb = 0.0; errors = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(upload, it): it for it in todo}
        for f in as_completed(futs):
            try:
                done_mb += f.result() / 1e6
            except Exception as e:  # keep going, report at the end
                errors.append((futs[f][1], str(e)[:200]))
            done += 1
            if done % 25 == 0 or done == len(todo):
                el = time.time() - t0
                print(f"  {done:,}/{len(todo):,} files | {done_mb:,.0f}/{total_mb:,.0f} MB | "
                      f"{done_mb / max(el, 1e-6):,.1f} MB/s")
    print(f"\nDONE in {(time.time() - t0) / 60:.1f} min | uploaded {done - len(errors):,} files")
    if errors:
        print(f"{len(errors)} errors (re-run the script to retry only the missing files):")
        for n, e in errors[:10]:
            print("  ", n, "->", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
