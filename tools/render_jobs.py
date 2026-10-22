#!/usr/bin/env python3
"""Fetch pending Reel jobs from the website, render each with make_reel.py,
commit the MP4s, then ping the website so it publishes them.
Runs inside GitHub Actions (free for public repos)."""
import json, os, re, subprocess, sys, time, urllib.request

SITE = "https://chinacargohub.com"
JOBS_URL = SITE + "/wp-json/ccb/v1/reel-jobs"
READY_URL = SITE + "/wp-json/ccb/v1/reel-ready"
UA = {"User-Agent": "Mozilla/5.0 (reel-bot; +https://github.com/tahirw456/social-reels)"}
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def get(url, binary=False):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
                return data if binary else json.loads(data.decode())
        except Exception as e:
            print("GET failed", url, e, file=sys.stderr)
            time.sleep(5)
    return None


def pending():
    jobs = get(JOBS_URL) or []
    out = []
    for j in jobs:
        jid = re.sub(r"[^a-z0-9-]", "", str(j.get("id", "")).lower())
        if jid and not os.path.exists(os.path.join(ROOT, "reels", jid + ".mp4")):
            j["id"] = jid
            out.append(j)
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--render"
    jobs = pending()
    if mode == "--check":
        print("pending=" + ("1" if jobs else "0"))
        return
    os.makedirs(os.path.join(ROOT, "reels"), exist_ok=True)
    os.makedirs("/tmp/reelwork", exist_ok=True)
    made = []
    for j in jobs:
        img = get(j["image"], binary=True)
        if not img:
            continue
        ip = "/tmp/reelwork/%s.jpg" % j["id"]
        open(ip, "wb").write(img)
        out = os.path.join(ROOT, "reels", j["id"] + ".mp4")
        cmd = ["python3", os.path.join(HERE, "make_reel.py"), "--image", ip, "--out", out,
               "--hook", j.get("hook", ""), "--cta", j.get("cta", ""), "--sub", j.get("sub", "Follow for more"),
               "--accent", j.get("accent", "#F28C28"), "--style", j.get("style", "sans"),
               "--seconds", str(j.get("seconds", 12))]
        if subprocess.run(cmd).returncode == 0 and os.path.exists(out):
            made.append(j["id"])
    if not made:
        return
    # keep the repo small: drop videos older than 3 days
    cutoff = time.time() - 3 * 86400
    for f in os.listdir(os.path.join(ROOT, "reels")):
        p = os.path.join(ROOT, "reels", f)
        if f.endswith(".mp4") and f[:-4] not in made:
            r = subprocess.run(["git", "log", "-1", "--format=%ct", "--", p], cwd=ROOT, capture_output=True, text=True)
            ts = int(r.stdout.strip() or 0)
            if ts and ts < cutoff:
                subprocess.run(["git", "rm", "-q", p], cwd=ROOT)
    subprocess.run(["git", "add", "reels"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Reels " + ", ".join(made)], cwd=ROOT, check=True)
    for i in range(3):
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT).returncode == 0:
            break
        subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=ROOT)
    time.sleep(20)  # let raw.githubusercontent.com catch up
    for jid in made:
        print("ready ping", jid, get(READY_URL + "?job=" + jid))


if __name__ == "__main__":
    main()
