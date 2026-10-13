"""Rapport hebdomadaire YouTube : nouvelles vidéos, format/thème (LLM), performance relative, actions.

Sans clé (démo, données du dépôt) :
    python agent/weekly_report.py --demo
En vrai (cron du lundi matin, n8n, GitHub Actions…) :
    YOUTUBE_API_KEY=... ANTHROPIC_API_KEY=... SLACK_WEBHOOK_URL=... python agent/weekly_report.py --days 28

Ce que fait l'agent, dans l'ordre :
1. récupère les vidéos publiées récemment (API YouTube) ;
2. les classe par format et thème avec Claude (prompt : agent/prompts/classify.md), ou par règles sans clé ;
3. calcule l'indice de performance : vues ÷ vues médianes des vidéos de même âge (référence : data/videos.csv) ;
4. écrit un rapport Markdown (reports/) et poste un résumé sur Slack.
Les chiffres sont calculés en Python ; le LLM ne fait que classer et, en option, rédiger le résumé
à partir de ces chiffres (on lui interdit d'en inventer).
"""
import argparse
import csv
import json
import os
import statistics
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from taxonomy import FORMAT_LABEL, THEME_LABEL, THEME_INTENT, rule_format, title_features  # noqa: E402

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
PROMPT = (ROOT / "agent" / "prompts" / "classify.md").read_text(encoding="utf-8")
AGE_COHORTS = [(30, "moins de 1 mois"), (91, "1 à 3 mois"), (183, "3 à 6 mois"), (365, "6 à 12 mois"),
               (730, "1 à 2 ans"), (1096, "2 à 3 ans"), (1461, "3 à 4 ans"), (10 ** 6, "4 ans et plus")]


def cohort_for(age_days: float) -> str:
    return next(name for limit, name in AGE_COHORTS if age_days < limit)


def load_baseline():
    rows = list(csv.DictReader(open(ROOT / "data" / "videos.csv", encoding="utf-8")))
    medians = {}
    for _, name in AGE_COHORTS:
        views = [int(r["views"]) for r in rows if r["cohort"] == name]
        if views:
            medians[name] = statistics.median(views)
    return rows, medians


# ---------------------------------------------------------------- classement


def call_claude(user_text: str, system: str, max_tokens: int = 2000) -> str:
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user_text}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data["content"])


def parse_labels(text: str, videos: list[dict]) -> dict:
    """Lit la réponse JSON du LLM ; ignore toute étiquette hors taxonomie."""
    start, end = text.find("["), text.rfind("]")
    items = json.loads(text[start:end + 1])
    valid_ids = {v["video_id"] for v in videos}
    out = {}
    for it in items:
        if it.get("id") in valid_ids and it.get("format") in FORMAT_LABEL and it.get("theme") in THEME_LABEL:
            out[it["id"]] = (it["format"], it["theme"], "llm")
    return out


def classify(videos: list[dict], llm=None) -> dict:
    """Format et thème par vidéo. llm(texte) -> réponse ; None = pas de clé, règles seulement."""
    labels = {}
    if llm:
        lines = "\n".join(f'{v["video_id"]} | {v["title"]} | {v["duration_min"]} min' for v in videos)
        try:
            labels = parse_labels(llm(lines), videos)
        except (ValueError, KeyError) as e:
            print(f"Réponse du LLM illisible ({e}) : repli sur les règles.", file=sys.stderr)
    for v in videos:
        if v["video_id"] not in labels:
            if v.get("format"):          # déjà étiquetée (mode démo)
                labels[v["video_id"]] = (v["format"], v["theme"], "historique")
            else:
                labels[v["video_id"]] = (rule_format(v["title"]), "strategie_patrimoine", "règles")
    return labels


# ---------------------------------------------------------------- rapport


def fmt_k(v: float) -> str:
    return f"{v / 1e6:.1f} M".replace(".", ",") if v >= 1e6 else f"{round(v / 1e3)} k" if v >= 1e3 else str(int(v))


def fmt_x(v: float) -> str:
    return f"×{v:.2f}".replace(".", ",")


def fmt_pct(v: float) -> str:
    return f"{v * 100:.0f}\u00a0%"


def build_report(videos: list[dict], labels: dict, medians: dict, baseline: list[dict], today: date) -> tuple[str, str]:
    for v in videos:
        v["cohort"] = cohort_for(v["age_days"])
        v["index"] = v["views"] / medians[v["cohort"]]
        v["format"], v["theme"], v["label_source"] = labels[v["video_id"]]
    videos.sort(key=lambda v: v["age_days"])

    lines = [f"# Rapport YouTube @Finary — {today.strftime('%d/%m/%Y')}", ""]
    idx = [v["index"] for v in videos]
    best = max(videos, key=lambda v: v["index"])
    lines += [f"**{len(videos)} vidéos récentes**, indice médian {fmt_x(statistics.median(idx))} "
              f"(1,00 = vidéo typique du même âge). En tête : « {best['title']} » ({fmt_x(best['index'])}).", ""]
    lines += ["| Vidéo | Âge | Vues | Indice | Format | Thème | Action |", "|---|---|---|---|---|---|---|"]
    actions = []
    for v in videos:
        if v["age_days"] < 14:
            act = "trop tôt pour juger"
        elif v["index"] >= 2:
            act = "décliner (Short, article, e-mail)"
            actions.append(f"« {v['title']} » fait {fmt_x(v['index'])} : la décliner en Short-bande-annonce, article SEO "
                           f"et e-mail aux inscrits intéressés par « {THEME_LABEL[v['theme']]} ».")
        elif v["index"] < 0.6 and v["format"] == "analyse_patrimoine":
            act = "tester un titre « récit »"
            actions.append(f"« {v['title']} » ({fmt_x(v['index'])}) : analyse sous la médiane, candidate au test 2 "
                           "(titre et ouverture racontés comme une histoire).")
        elif v["index"] < 0.6:
            act = "à surveiller"
        else:
            act = ""
        title = v["title"].replace("|", "/")
        lines.append(f"| [{title}](https://www.youtube.com/watch?v={v['video_id']}) | {v['age_days']} j | {fmt_k(v['views'])} | "
                     f"{fmt_x(v['index'])} | {FORMAT_LABEL[v['format']]} | {THEME_LABEL[v['theme']]} | {act} |")

    # mix de formats et part des thèmes proches du produit
    def share(rows, pred):
        return sum(1 for r in rows if pred(r)) / max(1, len(rows))
    last12 = [r for r in baseline if r["cohort"] in ("1 à 3 mois", "3 à 6 mois", "6 à 12 mois")]
    lines += ["", "## Mix de la période",
              f"- Thèmes proches d'un produit Finary : {fmt_pct(share(videos, lambda r: THEME_INTENT[r['theme']] == 'forte'))} "
              f"des vidéos récentes (référence 12 mois : {fmt_pct(share(last12, lambda r: THEME_INTENT[r['theme']] == 'forte'))}).",
              f"- Analyses de patrimoine : {fmt_pct(share(videos, lambda r: r['format'] == 'analyse_patrimoine'))} "
              f"(référence : {fmt_pct(share(last12, lambda r: r['format'] == 'analyse_patrimoine'))}).",
              f"- Titres avec un montant en € : {fmt_pct(share(videos, lambda r: title_features(r['title'])['montant_euros']))} "
              "(à format égal, ×1,36 dans l'historique)."]
    if actions:
        lines += ["", "## Actions proposées"] + [f"- {a}" for a in actions[:5]]
    sources = {v["label_source"] for v in videos}
    lines += ["", f"_Étiquettes : {', '.join(sorted(sources))}. Indice calculé sur la référence data/videos.csv._"]
    slack = (f"Rapport YouTube : {len(videos)} vidéos récentes, indice médian {fmt_x(statistics.median(idx))}. "
             f"En tête : {best['title']} ({fmt_x(best['index'])}). " + (actions[0] if actions else ""))
    return "\n".join(lines) + "\n", slack


# ---------------------------------------------------------------- sources


def demo_videos(baseline: list[dict]) -> list[dict]:
    """Les vidéos de moins de 3 mois du relevé, comme si elles venaient de sortir."""
    out = []
    for r in baseline:
        if r["cohort"] in ("moins de 1 mois", "1 à 3 mois"):
            out.append({"video_id": r["video_id"], "title": r["title"], "views": int(r["views"]),
                        "age_days": int(r["age_days_est"]), "duration_min": float(r["duration_min"]),
                        "format": r["format"], "theme": r["theme"]})
    return out


def api_videos(days: int) -> list[dict]:
    from youtube_api import channel_uploads, upload_ids, video_details
    since = datetime.now(timezone.utc).timestamp() - days * 86400
    since_iso = datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    playlist, _ = channel_uploads("@Finary")
    now = datetime.now(timezone.utc)
    out = []
    for v in video_details(upload_ids(playlist, since_iso)):
        if v["short_candidate"]:
            continue
        pub = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
        out.append({**v, "age_days": max(1, (now - pub).days)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="données du dépôt, sans aucune clé")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    baseline, medians = load_baseline()
    videos = demo_videos(baseline) if a.demo else api_videos(a.days)
    if not videos:
        print("Aucune nouvelle vidéo.")
        return
    llm = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        llm = lambda text: call_claude(text, PROMPT)  # noqa: E731
    labels = classify(videos, llm)
    today = date(2026, 10, 13) if a.demo else date.today()
    report, slack = build_report(videos, labels, medians, baseline, today)

    out = Path(a.out or ROOT / "reports" / (f"demo.md" if a.demo else f"{today.isoformat()}.md"))
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Rapport écrit : {out.relative_to(ROOT)}")
    if os.environ.get("SLACK_WEBHOOK_URL") and not a.demo:
        req = urllib.request.Request(os.environ["SLACK_WEBHOOK_URL"], data=json.dumps({"text": slack}).encode(),
                                     headers={"content-type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
        print("Résumé posté sur Slack.")


if __name__ == "__main__":
    main()
