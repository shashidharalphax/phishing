import dns.resolver
import requests
from ipwhois import IPWhois
import tldextract
from typing import Dict, List

def resolve_records(fqdn: str) -> Dict:
    res = dns.resolver.Resolver()
    data = {"A": [], "AAAA": [], "CNAME": [], "MX": [], "NS": [], "TXT": []}
    for rtype in list(data.keys()):
        try:
            ans = res.resolve(fqdn, rtype, lifetime=5)
            out = []
            for a in ans:
                s = str(a.target if hasattr(a, "target") else a).rstrip(".")
                out.append(s)
            data[rtype] = out
        except Exception:
            pass
    return data

def ip_whois_bulk(ips: List[str]) -> List[Dict]:
    out = []
    for ip in ips:
        if ":" in ip:  # skip IPv6 whois for speed
            continue
        try:
            w = IPWhois(ip).lookup_rdap(depth=1)
            out.append({
                "ip": ip,
                "asn": w.get("asn"),
                "asn_cidr": w.get("asn_cidr"),
                "asn_country_code": w.get("asn_country_code"),
                "asn_description": w.get("asn_description"),
            })
        except Exception:
            out.append({"ip": ip})
    return out

# Minimal RDAP using IANA bootstrap (open dataset)
IANA_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"

def rdap_for_domain(fqdn: str) -> Dict:
    try:
        ext = tldextract.extract(fqdn)
        registrable = f"{ext.domain}.{ext.suffix}"
        tld = ext.suffix.split(".")[-1]
        b = requests.get(IANA_BOOTSTRAP, timeout=10).json()
        services = b.get("services", [])
        base = None
        for svc in services:
            tlds, urls = svc
            if tld in tlds and urls:
                base = urls[0].rstrip("/")
                break
        if base:
            r = requests.get(f"{base}/domain/{registrable}", timeout=15)
            if r.ok:
                return r.json()
    except Exception:
        pass
    return {}

def enrich_candidate(fqdn: str) -> Dict:
    dnsrec = resolve_records(fqdn)
    ips = dnsrec.get("A", []) + dnsrec.get("AAAA", [])
    asn = ip_whois_bulk(ips) if ips else []
    rdap = rdap_for_domain(fqdn)
    return {"dns": dnsrec, "ips": ips, "asn": asn, "rdap": rdap}