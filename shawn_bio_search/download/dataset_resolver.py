"""Enumerate downloadable files for dataset records.

Each resolver returns either a list of file dicts
``{"name","url","size","checksum"}`` or a single instruction dict when the data
requires an external tool (SRA prefetch, GDC client, controlled-access).
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Callable, Dict, List, Optional

from ..sources._http import http_json


File = Dict[str, Any]


def _zenodo_id(record: Dict[str, Any]) -> str:
    acc = str(record.get("accession") or "")
    m = re.search(r"(\d+)$", acc)
    if m:
        return m.group(1)
    url = str(record.get("url") or "")
    m = re.search(r"zenodo\.org/records?/(\d+)", url)
    return m.group(1) if m else ""


def _enumerate_zenodo(record: Dict[str, Any]) -> List[File]:
    rec_id = _zenodo_id(record)
    if not rec_id:
        return []
    try:
        data = http_json(f"https://zenodo.org/api/records/{rec_id}")
    except Exception:
        return []
    out: List[File] = []
    for f in (data.get("files") or []):
        if not isinstance(f, dict):
            continue
        links = f.get("links") or {}
        url = links.get("self") or links.get("download") or ""
        name = f.get("key") or f.get("filename") or ""
        checksum = f.get("checksum") or ""
        out.append({
            "name": name,
            "url": url,
            "size": f.get("size"),
            "checksum": checksum,
        })
    return out


def _figshare_id(record: Dict[str, Any]) -> str:
    acc = str(record.get("accession") or "")
    m = re.search(r"(\d+)$", acc)
    if m:
        return m.group(1)
    url = str(record.get("url") or "")
    m = re.search(r"figshare\.com/.*/(\d+)(?:$|/|\?)", url)
    return m.group(1) if m else ""


def _enumerate_figshare(record: Dict[str, Any]) -> List[File]:
    rec_id = _figshare_id(record)
    if not rec_id:
        return []
    try:
        data = http_json(f"https://api.figshare.com/v2/articles/{rec_id}/files")
    except Exception:
        return []
    out: List[File] = []
    for f in data or []:
        if not isinstance(f, dict):
            continue
        out.append({
            "name": f.get("name") or "",
            "url": f.get("download_url") or "",
            "size": f.get("size"),
            "checksum": f.get("supplied_md5") or f.get("computed_md5") or "",
        })
    return out


def _enumerate_dryad(record: Dict[str, Any]) -> List[File]:
    doi = (record.get("doi") or "").strip()
    if not doi:
        acc = str(record.get("accession") or "")
        if acc.startswith("10."):
            doi = acc
    if not doi:
        return []
    encoded = urllib.parse.quote(doi, safe="")
    try:
        ds = http_json(f"https://datadryad.org/api/v2/datasets/{encoded}")
        version_links = ds.get("_links", {}) if isinstance(ds, dict) else {}
        latest_href = (version_links.get("stash:version") or {}).get("href")
        if not latest_href:
            return []
        files = http_json(f"https://datadryad.org{latest_href}/files")
    except Exception:
        return []
    out: List[File] = []
    for entry in (files.get("_embedded", {}).get("stash:files", []) if isinstance(files, dict) else []):
        if not isinstance(entry, dict):
            continue
        dl = (entry.get("_links") or {}).get("stash:download") or {}
        href = dl.get("href")
        if not href:
            continue
        out.append({
            "name": entry.get("path") or "",
            "url": f"https://datadryad.org{href}",
            "size": entry.get("size"),
            "checksum": entry.get("digest") or "",
        })
    return out


def _enumerate_geo(record: Dict[str, Any]) -> List[File]:
    acc = str(record.get("accession") or "").upper()
    if not acc.startswith("GSE"):
        return []
    suffix = acc[:-3] + "nnn" if len(acc) > 3 else "GSEnnn"
    base_url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{suffix}/{acc}/suppl/"
    return [{
        "name": f"{acc}_suppl_index.html",
        "url": base_url,
        "size": None,
        "checksum": "",
        "note": "Directory listing — fetch individual files manually or use dataset_resolver.list_geo_suppl",
    }]


def _enumerate_biostudies(record: Dict[str, Any]) -> List[File]:
    acc = str(record.get("accession") or "")
    if not acc:
        return []
    try:
        data = http_json(f"https://www.ebi.ac.uk/biostudies/api/v1/studies/{acc}/info")
    except Exception:
        return []
    out: List[File] = []
    for f in (data.get("files") or []) if isinstance(data, dict) else []:
        if not isinstance(f, dict):
            continue
        path = f.get("path") or ""
        if not path:
            continue
        out.append({
            "name": path,
            "url": f"https://www.ebi.ac.uk/biostudies/files/{acc}/{path}",
            "size": f.get("size"),
            "checksum": "",
        })
    return out


def _enumerate_ena(record: Dict[str, Any]) -> List[File]:
    acc = str(record.get("accession") or "")
    if not acc:
        return []
    url = (
        "https://www.ebi.ac.uk/ena/portal/api/filereport?"
        + urllib.parse.urlencode({"accession": acc, "result": "read_run", "format": "json",
                                  "fields": "run_accession,fastq_ftp,fastq_bytes,fastq_md5"})
    )
    try:
        data = http_json(url)
    except Exception:
        return []
    out: List[File] = []
    for row in data or []:
        if not isinstance(row, dict):
            continue
        ftp_list = (row.get("fastq_ftp") or "").split(";")
        sizes = (row.get("fastq_bytes") or "").split(";")
        md5s = (row.get("fastq_md5") or "").split(";")
        for i, ftp in enumerate(ftp_list):
            if not ftp:
                continue
            url = ftp if ftp.startswith("http") or ftp.startswith("ftp") else f"https://{ftp}"
            out.append({
                "name": ftp.rsplit("/", 1)[-1],
                "url": url,
                "size": int(sizes[i]) if i < len(sizes) and sizes[i].isdigit() else None,
                "checksum": md5s[i] if i < len(md5s) else "",
            })
    return out


def _enumerate_pride(record: Dict[str, Any]) -> List[File]:
    acc = str(record.get("accession") or "")
    if not acc:
        return []
    url = (
        "https://www.ebi.ac.uk/pride/ws/archive/v3/files/byProject?"
        + urllib.parse.urlencode({"accession": acc})
    )
    try:
        data = http_json(url)
    except Exception:
        return []
    out: List[File] = []
    for entry in data or []:
        if not isinstance(entry, dict):
            continue
        for loc in (entry.get("publicFileLocations") or []):
            value = (loc or {}).get("value")
            if value:
                out.append({
                    "name": entry.get("fileName") or "",
                    "url": value,
                    "size": entry.get("fileSizeBytes"),
                    "checksum": entry.get("checksum") or "",
                })
                break
    return out


def _enumerate_metabolights(record: Dict[str, Any]) -> List[File]:
    acc = str(record.get("accession") or "")
    if not acc:
        return []
    try:
        data = http_json(f"https://www.ebi.ac.uk/metabolights/ws/studies/{acc}/files")
    except Exception:
        return []
    out: List[File] = []
    for f in (data.get("study") or []) if isinstance(data, dict) else []:
        if not isinstance(f, dict):
            continue
        path = f.get("file") or ""
        if not path:
            continue
        out.append({
            "name": path,
            "url": f"https://www.ebi.ac.uk/metabolights/ws/studies/{acc}/files/{path}",
            "size": None,
            "checksum": "",
        })
    return out


def _enumerate_cellxgene(record: Dict[str, Any]) -> List[File]:
    acc = str(record.get("accession") or record.get("id") or "")
    if not acc:
        return []
    try:
        data = http_json(f"https://api.cellxgene.cziscience.com/dp/v1/datasets/{acc}/assets")
    except Exception:
        return []
    out: List[File] = []
    for asset in (data.get("assets") or []) if isinstance(data, dict) else []:
        if not isinstance(asset, dict):
            continue
        out.append({
            "name": asset.get("filename") or asset.get("filetype") or "",
            "url": asset.get("presigned_url") or asset.get("url") or "",
            "size": asset.get("filesize"),
            "checksum": "",
        })
    return out


_EXTERNAL_TOOL: Dict[str, Dict[str, Any]] = {
    "sra": {"tool": "prefetch", "note": "Install sra-tools; run `prefetch <acc>` in the destination directory."},
    "gdc": {"tool": "gdc-client", "note": "Install gdc-client; download via manifest from https://portal.gdc.cancer.gov/."},
    "bioproject": {"tool": "prefetch", "note": "Resolve BioProject to SRA accessions, then use sra-tools."},
    "dbgap": {"tool": "sra-toolkit (controlled access)", "note": "Requires dbGaP approval and prefetch with dbGaP key."},
    "tcga": {"tool": "gdc-client", "note": "Use gdc-client with a GDC manifest (authentication may be required)."},
}


_NO_URL_REPOS = {"bigd", "bigd/gsa", "gsa", "cngb", "cngbdb", "ddbj", "datacite"}


_RESOLVERS: Dict[str, Callable[[Dict[str, Any]], List[File]]] = {
    "zenodo": _enumerate_zenodo,
    "figshare": _enumerate_figshare,
    "dryad": _enumerate_dryad,
    "geo": _enumerate_geo,
    "arrayexpress": _enumerate_biostudies,
    "biostudies": _enumerate_biostudies,
    "ena": _enumerate_ena,
    "pride": _enumerate_pride,
    "metabolights": _enumerate_metabolights,
    "cellxgene": _enumerate_cellxgene,
}


def enumerate_dataset_files(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a plan dict for a dataset record.

    Result shape:
      {"kind": "files", "files": [...]}
      {"kind": "external", "tool": ..., "args": [...], "note": ...}
      {"kind": "no-url", "note": ...}
    """
    repo = str(record.get("repository") or "").strip().lower()
    acc = str(record.get("accession") or "").strip()

    resolver = _RESOLVERS.get(repo)
    if resolver is not None:
        files = resolver(record)
        return {"kind": "files", "files": files}

    if repo in _EXTERNAL_TOOL:
        spec = _EXTERNAL_TOOL[repo]
        return {
            "kind": "external",
            "tool": spec["tool"],
            "args": [acc] if acc else [],
            "note": spec["note"],
        }

    if repo in _NO_URL_REPOS:
        url = (record.get("url") or "").strip()
        return {
            "kind": "no-url",
            "note": f"Repository '{repo or 'unknown'}' provides only a landing page; open {url or 'the record URL'} manually.",
        }

    return {"kind": "no-url", "note": f"No resolver for repository '{repo}'."}
