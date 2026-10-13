"""Collecte via l'API YouTube Data v3 (chiffres exacts : date, vues, likes, commentaires, durée).

    YOUTUBE_API_KEY=... python agent/youtube_api.py @Finary --out data/api_snapshot.csv

Quota : ~1 unité par lot de 50 vidéos, soit une vingtaine d'unités pour toute la chaîne
(quota gratuit : 10 000 unités par jour). Aucune dépendance hors bibliothèque standard.
"""
import argparse
import csv
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date

API = "https://www.googleapis.com/youtube/v3/"


def _get(endpoint: str, **params) -> dict:
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def iso_minutes(d: str) -> float:
    """PT1H2M3S -> 62.05"""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0.0
    days, h, mi, s = (int(x or 0) for x in m.groups())
    return round(days * 1440 + h * 60 + mi + s / 60, 2)


def channel_uploads(handle: str) -> tuple[str, dict]:
    ch = _get("channels", part="contentDetails,statistics", forHandle=handle)["items"][0]
    return ch["contentDetails"]["relatedPlaylists"]["uploads"], ch["statistics"]


def upload_ids(playlist_id: str, since: str | None = None) -> list[str]:
    ids, token = [], None
    while True:
        page = _get("playlistItems", part="contentDetails", playlistId=playlist_id, maxResults=50,
                    **({"pageToken": token} if token else {}))
        for it in page["items"]:
            if since and it["contentDetails"].get("videoPublishedAt", "") < since:
                return ids  # la playlist est triée du plus récent au plus ancien
            ids.append(it["contentDetails"]["videoId"])
        token = page.get("nextPageToken")
        if not token:
            return ids


def video_details(ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        page = _get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
        for v in page["items"]:
            st = v.get("statistics", {})
            minutes = iso_minutes(v["contentDetails"]["duration"])
            out.append({
                "video_id": v["id"],
                "title": v["snippet"]["title"],
                "published_at": v["snippet"]["publishedAt"],
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "duration_min": minutes,
                # l'API ne dit pas si c'est un Short : ≤ 3 min = Short probable
                "short_candidate": int(minutes <= 3),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("handle", nargs="?", default="@Finary")
    ap.add_argument("--since", help="ISO 8601, ex. 2026-09-01T00:00:00Z")
    ap.add_argument("--out", default=f"data/api_snapshot_{date.today().isoformat()}.csv")
    a = ap.parse_args()
    playlist, stats = channel_uploads(a.handle)
    rows = video_details(upload_ids(playlist, a.since))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} vidéos -> {a.out} (abonnés : {stats.get('subscriberCount')})")


if __name__ == "__main__":
    main()
