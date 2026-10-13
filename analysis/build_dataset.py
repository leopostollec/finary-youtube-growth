"""Construit data/videos.csv à partir de l'export brut de la chaîne (data/raw/).

Relevé du 13/10/2026 sur la page publique youtube.com/@Finary : 389 vidéos longues + 1 live,
et les 48 Shorts les plus récents. Vues arrondies comme sur la page (« 218 k »),
dates relatives (« il y a 1 an »). Pour des chiffres exacts (date, likes, commentaires),
relancer la collecte avec l'API YouTube : agent/youtube_api.py.
"""
import csv
import re
from datetime import date, timedelta
from pathlib import Path

from taxonomy import FORMATS, THEMES, rule_format, title_features

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SNAPSHOT = date(2026, 10, 13)
UNIT_DAYS = {"d": 1, "w": 7, "m": 30.44, "y": 365.25}

# Cohortes d'âge : on ne compare une vidéo qu'à celles publiées à la même époque
COHORTS = [
    ("moins de 1 mois", lambda u, n: u in "dw"),
    ("1 à 3 mois", lambda u, n: u == "m" and n < 3),
    ("3 à 6 mois", lambda u, n: u == "m" and 3 <= n < 6),
    ("6 à 12 mois", lambda u, n: u == "m" and n >= 6),
    ("1 à 2 ans", lambda u, n: u == "y" and n == 1),
    ("2 à 3 ans", lambda u, n: u == "y" and n == 2),
    ("3 à 4 ans", lambda u, n: u == "y" and n == 3),
    ("4 ans et plus", lambda u, n: u == "y" and n >= 4),
]


def clean(title: str) -> str:
    title = re.sub(r"[⁦-⁩​‎‏️]", "", title)
    return re.sub(r"[    ]", " ", title).strip()


def read_rows(path: Path, n_fields: int):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            yield line.split(";", n_fields - 1)


def parse_age(age: str):
    m = re.fullmatch(r"(\d+)([dwmy])", age)
    n, unit = int(m.group(1)), m.group(2)
    days = UNIT_DAYS[unit]
    # YouTube arrondit vers le bas : « il y a 1 an » = entre 12 et 23 mois
    newest = SNAPSHOT - timedelta(days=round(n * days))
    oldest = SNAPSHOT - timedelta(days=round((n + 1) * days))
    age_days = round((n + 0.5) * days)
    cohort = next(name for name, test in COHORTS if test(unit, n))
    return age_days, oldest, newest, cohort


def main():
    labels = {r[0]: (r[1], r[2]) for r in read_rows(RAW / "labels_llm.txt", 3)}

    sources = [("video", RAW / "videos_part1.txt"), ("video", RAW / "videos_part2.txt"), ("live", RAW / "live.txt")]
    out = []
    for kind, path in sources:
        for vid, views, age, dur, title in read_rows(path, 5):
            title = clean(title)
            age_days, oldest, newest, cohort = parse_age(age)
            f_code, t_code = labels[vid]
            row = {
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": title,
                "kind": kind,
                "views": int(views),
                "age_label": age,
                "age_days_est": age_days,
                "published_between": f"{oldest.isoformat()}/{newest.isoformat()}",
                "cohort": cohort,
                "duration_min": round(int(dur) / 60, 1),
                "format": FORMATS[f_code][0],
                "theme": THEMES[t_code][0],
                "format_rules": rule_format(title),
            }
            row.update({f"t_{k}": int(v) for k, v in title_features(title).items()})
            row["title_len"] = len(title)
            out.append(row)

    ids = [r["video_id"] for r in out]
    assert len(ids) == len(set(ids)) == len(labels), "étiquettes et vidéos ne correspondent pas"

    with open(ROOT / "data" / "videos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    shorts = [{"video_id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "views": int(v), "title": clean(t)}
              for vid, v, t in read_rows(RAW / "shorts_latest48.txt", 3)]
    with open(ROOT / "data" / "shorts_latest48.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(shorts[0].keys()))
        w.writeheader()
        w.writerows(shorts)

    print(f"{len(out)} vidéos longues, {len(shorts)} Shorts -> data/videos.csv, data/shorts_latest48.csv")


if __name__ == "__main__":
    main()
