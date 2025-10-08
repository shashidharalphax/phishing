from typing import Tuple
from rapidfuzz import fuzz
import tldextract

RISK_TLDS = {"tk","ml","ga","cf","gq"}
PROXY_TUNNEL_HOSTS = {"ngrok.io","trycloudflare.com","loca.lt","serveo.net","pages.dev","github.io","cloudfront.net"}

def classify_candidate(target, cand, meta, sim) -> Tuple[str, float, str]:
    ext_t = tldextract.extract(target.domain)
    ext_c = tldextract.extract(cand.fqdn)
    brand = (target.brand or ext_t.domain).lower()

    lex = fuzz.WRatio(brand, ext_c.domain) / 100.0
    score = 0.0
    reason = "unknown"

    if 0.75 <= lex < 1.0 and f"{ext_c.domain}.{ext_c.suffix}" != f"{ext_t.domain}.{ext_t.suffix}":
        reason = "typosquatting"; score += 0.4

    if ext_c.domain != ext_t.domain and brand in ext_c.subdomain:
        reason = "subdomain"; score += 0.3

    if f"{ext_c.domain}.{ext_c.suffix}" in PROXY_TUNNEL_HOSTS:
        reason = "tunneling"; score += 0.2

    score += 0.25*float(sim.get("img_sim",0)) + 0.25*float(sim.get("html_sim",0))

    # Conservative thresholds
    score = min(1.0, score)
    if score >= 0.75:
        label = "IDENTIFIED_PHISHING"
    elif score >= 0.50:
        label = "SUSPECTED"
    else:
        label = "CLEAN"

    return label, float(score), reason