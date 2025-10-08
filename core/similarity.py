from PIL import Image
import imagehash
import cv2
import numpy as np
from bs4 import BeautifulSoup
from simhash import Simhash

def _read_html(path: str) -> str:
    try:
        return open(path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""

def html_struct_hash(html: str):
    soup = BeautifulSoup(html or "", "html.parser")
    tags = [t.name for t in soup.find_all()]
    text = " ".join([t.get_text(" ", strip=True) for t in soup.find_all(["title","h1","h2","h3","p","a","button","span"])])
    tokens = tags + text.split()
    return Simhash(tokens)

def img_similarity(p1: str, p2: str):
    phash_str = ""
    sim_phash = 0.0
    orb_ratio = 0.0
    try:
        h1 = imagehash.phash(Image.open(p1))
        h2 = imagehash.phash(Image.open(p2))
        phash_str = str(h2)
        sim_phash = 1 - (h1 - h2) / 64.0
    except Exception:
        pass
    try:
        img1 = cv2.imdecode(np.fromfile(p1, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imdecode(np.fromfile(p2, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if img1 is not None and img2 is not None:
            orb = cv2.ORB_create()
            kp1, des1 = orb.detectAndCompute(img1, None)
            kp2, des2 = orb.detectAndCompute(img2, None)
            if des1 is not None and des2 is not None:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                matches = sorted(matches, key=lambda x: x.distance)[:50]
                if matches:
                    distances = [m.distance for m in matches]
                    orb_ratio = 1 - (sum(distances)/len(distances))/100.0
                    orb_ratio = max(0.0, min(1.0, orb_ratio))
    except Exception:
        pass
    return phash_str, float(0.7*sim_phash + 0.3*orb_ratio)

def compute_similarity(orig_img: str, cand_img: str, cand_url: str = ""):
    phash, img_sim = img_similarity(orig_img, cand_img)
    h1 = html_struct_hash(_read_html(orig_img.replace(".png",".html")))
    h2 = html_struct_hash(_read_html(cand_img.replace(".png",".html")))
    try:
        hd = h1.distance(h2)
        html_sim = 1 - hd/64.0
        html_hash = str(h2.value)
    except Exception:
        html_sim = 0.0; html_hash = ""
    return {"phash": phash, "img_sim": img_sim, "html_hash": html_hash, "html_sim": html_sim}