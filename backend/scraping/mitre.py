import os
from datetime import datetime
import re
from typing import List, Tuple, Optional

import requests
from bs4 import BeautifulSoup


MITRE_ENTERPRISE_URL = "https://attack.mitre.org/techniques/enterprise/"
MITRE_GROUPS_URL = "https://attack.mitre.org/groups/"
MITRE_MOBILE_TACTICS_URL = "https://attack.mitre.org/tactics/mobile/"
MITRE_ICS_TACTICS_URL = "https://attack.mitre.org/tactics/ics/"
MITRE_MITIGATIONS_ENTERPRISE_URL = "https://attack.mitre.org/mitigations/enterprise/"
MITRE_MITIGATIONS_MOBILE_URL = "https://attack.mitre.org/mitigations/mobile/"
MITRE_MITIGATIONS_ICS_URL = "https://attack.mitre.org/mitigations/ics/"


def _scrape_listing_table(
    url: str,
    id_regex: str,
    href_prefix: str,
    href_extract_regex: str,
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Generic table scraper for MITRE list pages (Groups, Mobile tactics, etc.).
    Returns a list of (id, name, url, description).
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results: List[Tuple[str, str, str, str]] = []

    def extract_id_from_href(href: str) -> Optional[str]:
        m = re.search(href_extract_regex, href)
        return m.group(1) if m else None

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            item_id: Optional[str] = None
            name: Optional[str] = None
            item_url: Optional[str] = None
            desc: str = ""

            # Attempt 1: first cell matches the ID pattern, second is name
            first_text = tds[0].get_text(strip=True)
            if re.match(id_regex, first_text or ""):
                item_id = first_text
                name_cell = tds[1] if len(tds) > 1 else tds[0]
                name = name_cell.get_text(strip=True)
                a = name_cell.find("a", href=True) or tds[0].find("a", href=True)
                if a and a.get("href", "").startswith(href_prefix):
                    item_url = f"https://attack.mitre.org{a['href']}"
                # Description: prefer longest text from remaining cells
                if len(tds) > 2:
                    cand = [
                        td.get_text(" ", strip=True)
                        for td in tds[2:]
                        if td.get_text(strip=True)
                    ]
                    if cand:
                        desc = max(cand, key=len)

            # Attempt 2: derive from any matching link in the row
            if not item_id or not item_url:
                a = tr.find("a", href=True)
                if a and href_prefix in a.get("href", ""):
                    derived = extract_id_from_href(a["href"])
                    if derived:
                        item_id = item_id or derived
                        item_url = item_url or f"https://attack.mitre.org{a['href']}"
                        # Name: prefer second cell if present, else fallback to first text
                        texts = [
                            td.get_text(" ", strip=True)
                            for td in tds
                            if td.get_text(strip=True)
                        ]
                        if len(tds) > 1:
                            name = name or tds[1].get_text(" ", strip=True)
                        elif texts:
                            name = name or texts[0]
                        # Description: longest among remaining cells beyond second
                        rem = [
                            td.get_text(" ", strip=True)
                            for td in tds[2:]
                            if td.get_text(strip=True)
                        ]
                        if rem and not desc:
                            desc = max(rem, key=len)

            if item_id and name and item_url:
                desc = re.sub(r"\s+", " ", desc or "").strip()
                results.append((item_id, name, item_url, desc))

            if limit and len(results) >= limit:
                break
        if limit and len(results) >= limit:
            break

    return results


def _is_technique_id(text: str) -> bool:
    return bool(re.match(r"^T\d+$", text))


def _is_subtech_code(text: str) -> bool:
    return bool(re.match(r"^\.\d{3}$", text))


def collect_mitre_enterprise_techniques(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str]]:
    """
    Scrape MITRE ATT&CK Enterprise techniques table and return a list of
    (technique_id, technique_name, url) tuples. Includes sub-techniques as TXXXX.XXX.
    """
    resp = requests.get(MITRE_ENTERPRISE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results: List[Tuple[str, str, str]] = []
    current_tech_id: Optional[str] = None

    # Iterate tables and rows; identify technique and sub-technique rows by column content
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            # Technique row: first cell is like T1548, second is the name
            id_text = tds[0].get_text(strip=True)
            if _is_technique_id(id_text):
                name_cell = tds[1] if len(tds) > 1 else tds[0]
                name_text = name_cell.get_text(strip=True)

                # Prefer URL from anchor in either id or name cell
                href = None
                for cell in (tds[0], name_cell):
                    a = cell.find("a", href=True)
                    if a and a["href"].startswith("/techniques/T"):
                        href = a["href"]
                        break
                url = (
                    f"https://attack.mitre.org{href}"
                    if href
                    else f"https://attack.mitre.org/techniques/{id_text}/"
                )

                results.append((id_text, name_text, url))
                current_tech_id = id_text
                continue

            # Sub-technique row: second cell is like .001, third is the name
            if len(tds) >= 3:
                subcode_text = tds[1].get_text(strip=True)
                if _is_subtech_code(subcode_text) and current_tech_id:
                    sub_id = f"{current_tech_id}{subcode_text}"
                    sub_name = tds[2].get_text(strip=True)

                    # Try to resolve sub-technique URL
                    href = None
                    for cell in (tds[1], tds[2]):
                        a = cell.find("a", href=True)
                        if a and a["href"].startswith("/techniques/T"):
                            href = a["href"]
                            break
                    url = (
                        f"https://attack.mitre.org{href}"
                        if href
                        else f"https://attack.mitre.org/techniques/{current_tech_id}/{subcode_text[1:]}/"
                    )

                    results.append((sub_id, sub_name, url))

            if limit and len(results) >= limit:
                break
        if limit and len(results) >= limit:
            break

    return results


def collect_mitre_mobile_tactics(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scrape MITRE ATT&CK Mobile tactics listing and return a list of
    (tactic_id, tactic_name, url, description) tuples. Tactic IDs are like TA0001.
    """
    return _scrape_listing_table(
        url=MITRE_MOBILE_TACTICS_URL,
        id_regex=r"^TA\d{4}$",
        href_prefix="/tactics/",
        href_extract_regex=r"/tactics/(TA\d{4})/?",
        limit=limit,
    )


def collect_mitre_ics_tactics(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scrape MITRE ATT&CK ICS tactics listing and return a list of
    (tactic_id, tactic_name, url, description) tuples. Tactic IDs are like TA0001.
    """
    return _scrape_listing_table(
        url=MITRE_ICS_TACTICS_URL,
        id_regex=r"^TA\d{4}$",
        href_prefix="/tactics/",
        href_extract_regex=r"/tactics/(TA\d{4})/?",
        limit=limit,
    )


def write_mitre_output(entries: List[Tuple[str, str, str]], output_path: str) -> None:
    lines = [f"{tid} - {name} - {url}" for tid, name, url in entries]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def collect_mitre_groups(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scrape MITRE ATT&CK Groups listing and return a list of
    (group_id, group_name, url, description) tuples. Group IDs are like G0001.
    """
    return _scrape_listing_table(
        url=MITRE_GROUPS_URL,
        id_regex=r"^G\d{4}$",
        href_prefix="/groups/",
        href_extract_regex=r"/groups/(G\d{4})/?",
        limit=limit,
    )


def collect_mitre_mitigations_enterprise(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scrape MITRE ATT&CK Enterprise mitigations listing and return a list of
    (mitigation_id, mitigation_name, url, description) tuples. Mitigation IDs are like M1047.
    """
    return _scrape_listing_table(
        url=MITRE_MITIGATIONS_ENTERPRISE_URL,
        id_regex=r"^M\d{4}$",
        href_prefix="/mitigations/",
        href_extract_regex=r"/mitigations/(M\d{4})/?",
        limit=limit,
    )


def collect_mitre_mitigations_mobile(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scrape MITRE ATT&CK Mobile mitigations listing and return a list of
    (mitigation_id, mitigation_name, url, description) tuples. Mitigation IDs are like M1047.
    """
    return _scrape_listing_table(
        url=MITRE_MITIGATIONS_MOBILE_URL,
        id_regex=r"^M\d{4}$",
        href_prefix="/mitigations/",
        href_extract_regex=r"/mitigations/(M\d{4})/?",
        limit=limit,
    )


def collect_mitre_mitigations_ics(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scrape MITRE ATT&CK ICS mitigations listing and return a list of
    (mitigation_id, mitigation_name, url, description) tuples. Mitigation IDs are like M1047.
    """
    return _scrape_listing_table(
        url=MITRE_MITIGATIONS_ICS_URL,
        id_regex=r"^M\d{4}$",
        href_prefix="/mitigations/",
        href_extract_regex=r"/mitigations/(M\d{4})/?",
        limit=limit,
    )


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(here, "mitre_enterprise_techniques.txt")
    groups_output_path = os.path.join(here, "MITRE/mitre_groups.txt")
    mobile_tactics_output_path = os.path.join(here, "MITRE/mitre_mobile_tactics.txt")
    ics_tactics_output_path = os.path.join(here, "MITRE/mitre_ics_tactics.txt")
    mitigations_enterprise_output_path = os.path.join(
        here, "MITRE/mitre_mitigations_enterprise.txt"
    )
    mitigations_mobile_output_path = os.path.join(
        here, "MITRE/mitre_mitigations_mobile.txt"
    )
    mitigations_ics_output_path = os.path.join(here, "MITRE/mitre_mitigations_ics.txt")

    entries = collect_mitre_enterprise_techniques()
    write_mitre_output(entries, output_path)
    print(f"Wrote {len(entries)} lines to: {output_path}")

    groups = collect_mitre_groups()
    # Write as: ID - Name - URL - Description (one per line)
    with open(groups_output_path, "w", encoding="utf-8") as gf:
        for gid, name, url, desc in groups:
            gf.write(f"{gid} - {name} - {url} - {desc}\n\n")
    print(f"Wrote {len(groups)} lines to: {groups_output_path}")

    mobile_tactics = collect_mitre_mobile_tactics()
    with open(mobile_tactics_output_path, "w", encoding="utf-8") as mf:
        for tid, name, url, desc in mobile_tactics:
            mf.write(f"{tid} - {name} - {url} - {desc}\n\n")
    print(f"Wrote {len(mobile_tactics)} lines to: {mobile_tactics_output_path}")

    ics_tactics = collect_mitre_ics_tactics()
    with open(ics_tactics_output_path, "w", encoding="utf-8") as tf:
        for tid, name, url, desc in ics_tactics:
            tf.write(f"{tid} - {name} - {url} - {desc}\n\n")
    print(f"Wrote {len(ics_tactics)} lines to: {ics_tactics_output_path}")

    mitigations_enterprise = collect_mitre_mitigations_enterprise()
    with open(mitigations_enterprise_output_path, "w", encoding="utf-8") as ef:
        for mid, name, url, desc in mitigations_enterprise:
            ef.write(f"{mid} - {name} - {url} - {desc}\n\n")
    print(
        f"Wrote {len(mitigations_enterprise)} lines to: {mitigations_enterprise_output_path}"
    )

    mitigations_mobile = collect_mitre_mitigations_mobile()
    with open(mitigations_mobile_output_path, "w", encoding="utf-8") as mf2:
        for mid, name, url, desc in mitigations_mobile:
            mf2.write(f"{mid} - {name} - {url} - {desc}\n\n")
    print(f"Wrote {len(mitigations_mobile)} lines to: {mitigations_mobile_output_path}")

    mitigations_ics = collect_mitre_mitigations_ics()
    with open(mitigations_ics_output_path, "w", encoding="utf-8") as if2:
        for mid, name, url, desc in mitigations_ics:
            if2.write(f"{mid} - {name} - {url} - {desc}\n\n")
    print(f"Wrote {len(mitigations_ics)} lines to: {mitigations_ics_output_path}")


if __name__ == "__main__":
    main()
