"""Analyse de data/videos.csv -> analysis/results.json (lu par le tableau de bord docs/).

Mesure clé : l'indice de performance = vues / médiane des vues de la même cohorte d'âge.
Une vidéo à 2,0 a fait deux fois plus de vues que la vidéo typique publiée à la même époque :
on compare ainsi des vidéos de 2022 et de 2026 sans que l'ancienneté ou la croissance
de la chaîne faussent la comparaison. Les vidéos de moins d'un mois sont exclues des comparaisons.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from build_dataset import COHORTS, SNAPSHOT
from taxonomy import FORMAT_LABEL, THEME_INTENT, THEME_LABEL, TITLE_FEATURES

ADJUSTED_FEATURES = ["montant_euros", "superlatif", "vous", "je", "riche", "majuscules", "question", "secret"]


def adjusted_effects(comp: pd.DataFrame, n_boot: int = 2000, seed: int = 7):
    """Effet de chaque motif de titre « à format égal » : régression de log(indice) sur
    le format + les motifs, intervalle de confiance à 90 % par bootstrap."""
    X = pd.get_dummies(comp.format).astype(float).drop(columns=["analyse_patrimoine"])
    for f in ADJUSTED_FEATURES:
        X[f] = comp[f"t_{f}"].astype(float)
    X.insert(0, "const", 1.0)
    y = np.log(comp.perf_index.values)
    beta = np.linalg.lstsq(X.values, y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        boots.append(np.linalg.lstsq(X.values[i], y[i], rcond=None)[0])
    lo, hi = np.percentile(np.array(boots), [5, 95], axis=0)
    out = {}
    for name, b, l, h in zip(X.columns, beta, lo, hi):
        out[name] = {"x": round(float(np.exp(b)), 2), "lo": round(float(np.exp(l)), 2), "hi": round(float(np.exp(h)), 2)}
    return out

ROOT = Path(__file__).resolve().parent.parent
MIN_GROUP = 8  # en dessous, on n'affiche pas de médiane (trop peu de vidéos)


def r2(x):
    return None if pd.isna(x) else round(float(x), 2)


def group_stats(df, key, labels):
    total_n, total_views = len(df), df.views.sum()
    rows = []
    for k, g in df.groupby(key):
        rows.append({
            "key": k, "label": labels.get(k, k), "n": int(len(g)),
            "share_videos": r2(len(g) / total_n), "share_views": r2(g.views.sum() / total_views),
            "median_index": r2(g.perf_index.median()) if len(g) >= MIN_GROUP else None,
            "median_views": int(g.views.median()),
        })
    return sorted(rows, key=lambda r: (r["median_index"] is None, -(r["median_index"] or 0)))


def main():
    df = pd.read_csv(ROOT / "data" / "videos.csv")
    shorts = pd.read_csv(ROOT / "data" / "shorts_latest48.csv")

    df["cohort_median"] = df.groupby("cohort").views.transform("median")
    df["perf_index"] = df.views / df.cohort_median
    comp = df[df.cohort != "moins de 1 mois"].copy()          # base de comparaison
    last12 = df[df.cohort.isin(["moins de 1 mois", "1 à 3 mois", "3 à 6 mois", "6 à 12 mois"])]
    before = df[~df.index.isin(last12.index)]

    order = [name for name, _ in COHORTS]
    trend = []
    for name in reversed(order):
        g = df[df.cohort == name]
        trend.append({"cohort": name, "n": int(len(g)), "median_views": int(g.views.median()),
                      "p25": int(g.views.quantile(.25)), "p75": int(g.views.quantile(.75))})

    # mix de formats : 12 derniers mois vs avant
    mix = []
    for k in FORMAT_LABEL:
        a = (last12.format == k).mean()
        b = (before.format == k).mean()
        mix.append({"key": k, "label": FORMAT_LABEL[k], "share_last12": r2(a), "share_before": r2(b)})

    feats = []
    for key, (label, _rx) in TITLE_FEATURES.items():
        col = f"t_{key}"
        w, wo = comp[comp[col] == 1], comp[comp[col] == 0]
        if len(w) < MIN_GROUP or len(wo) < MIN_GROUP:
            continue
        feats.append({"key": key, "label": label, "n_with": int(len(w)),
                      "median_with": r2(w.perf_index.median()), "median_without": r2(wo.perf_index.median()),
                      "lift": r2(w.perf_index.median() / wo.perf_index.median())})
    feats.sort(key=lambda f: -f["lift"])
    adj = adjusted_effects(comp)
    for f in feats:
        if f["key"] in adj:
            f["adjusted"] = adj[f["key"]]
    format_effects = {k: adj[k] for k in adj if k in FORMAT_LABEL}

    # croisement format x thème (au moins 5 vidéos) : où se rencontrent audience et intention
    matrix = []
    for (fmt, th), g in comp.groupby(["format", "theme"]):
        if len(g) >= 5:
            matrix.append({"format": fmt, "format_label": FORMAT_LABEL[fmt], "theme": th, "theme_label": THEME_LABEL[th],
                           "intent": THEME_INTENT[th], "n": int(len(g)), "median_index": r2(g.perf_index.median()),
                           "share_views": r2(g.views.sum() / comp.views.sum())})
    matrix.sort(key=lambda m: -m["median_index"])
    intent = []
    for level in ["forte", "moyenne", "faible", "produit"]:
        g = comp[comp.theme.map(THEME_INTENT) == level]
        intent.append({"intent": level, "n": int(len(g)), "share_videos": r2(len(g) / len(comp)),
                       "share_views": r2(g.views.sum() / comp.views.sum()), "median_index": r2(g.perf_index.median())})
        g12 = last12[last12.theme.map(THEME_INTENT) == level]
        intent[-1]["share_uploads_last12"] = r2(len(g12) / len(last12))
        gb = before[before.theme.map(THEME_INTENT) == level]
        intent[-1]["share_uploads_before"] = r2(len(gb) / len(before))

    bins = [0, 10, 20, 30, 45, 1000]
    names = ["moins de 10 min", "10 à 20 min", "20 à 30 min", "30 à 45 min", "45 min et plus"]
    # durée : hors vidéos produit (des démos courtes qui fausseraient la comparaison)
    content = comp[comp.format != "finary_produit"].copy()
    content["dur_bucket"] = pd.cut(content.duration_min, bins=bins, labels=names, right=False)
    durations = [{"bucket": n, "n": int((content.dur_bucket == n).sum()),
                  "median_index": r2(content[content.dur_bucket == n].perf_index.median())} for n in names]

    # analyses de patrimoine : avec ou sans le libellé « Analyse de patrimoine » dans le titre (12 derniers mois + 1-2 ans)
    ap = comp[(comp.format == "analyse_patrimoine")]
    ap_recent = ap[ap.cohort.isin(["1 à 3 mois", "3 à 6 mois", "6 à 12 mois", "1 à 2 ans"])]
    serie = {
        "with_label": {"n": int((ap_recent.t_libelle_serie == 1).sum()),
                       "median_index": r2(ap_recent[ap_recent.t_libelle_serie == 1].perf_index.median())},
        "without_label": {"n": int((ap_recent.t_libelle_serie == 0).sum()),
                          "median_index": r2(ap_recent[ap_recent.t_libelle_serie == 0].perf_index.median())},
    }

    # ---- chiffres qui fondent les recommandations
    def ex(rows, n=3):
        return [{"title": t, "index": r2(i), "views": int(v)} for t, i, v in zip(rows.title[:n], rows.perf_index[:n], rows.views[:n])]
    year = comp.title.str.contains(r"20(?:2[4-7])")
    guides = comp[(comp.format == "cours_guide") & comp.title.str.contains("guide complet|guide pour débutant|guide débutant|guide pratique pour débutants", case=False)]
    ana = comp[comp.format == "analyse_patrimoine"].sort_values("perf_index", ascending=False)
    famous = ana.title.str.contains("Macron|Attal|Bayrou|gouvernement|footballer|rugbyman|youtubeur|Moubeche|DJ ", case=False)
    niche = ana.title.str.contains("Invalide|expatrié|divorce|vendant son entreprise|Indonésie", case=False)
    sh = shorts.copy()
    sh["group"] = "autres"
    sh.loc[sh.title.str.contains("riche|milliard|fortune|Arnault|royale|Tyson|Federer|Président", case=False), "group"] = "richesse"
    sh.loc[sh.title.str.contains("Finary|transférer vos cryptos|migrer vos cryptos", case=False), "group"] = "produit"
    sh.loc[sh.title.str.contains("vidéo compl|sur la chaîne|enquête complète|sur notre chaîne", case=False), "group"] = "annonce"
    reco = {
        "year_in_title": {"n": int(year.sum()), "median_with": r2(comp[year].perf_index.median()),
                          "median_without": r2(comp[~year].perf_index.median())},
        "guides": sorted(ex(guides.sort_values("perf_index", ascending=False), 8), key=lambda g: -g["index"]),
        "analyses_top": ex(ana, 3),
        "analyses_famous": {"n": int(famous.sum()), "median": r2(ana[famous].perf_index.median()),
                            "median_others": r2(ana[~famous].perf_index.median())},
        "analyses_niche": {"n": int(niche.sum()), "median": r2(ana[niche].perf_index.median())},
        "shorts_groups": {g: {"n": int((sh.group == g).sum()), "median_views": int(sh[sh.group == g].views.median())}
                          for g in ["richesse", "autres", "produit", "annonce"]},
        "n_over_6x": int((comp.perf_index > 6).sum()),
    }

    cols = ["video_id", "url", "title", "views", "cohort", "duration_min", "format", "theme", "perf_index"]
    top = comp.sort_values("perf_index", ascending=False).head(15)[cols]
    bottom_formats = comp.sort_values("perf_index").head(10)[cols]

    rules_decided = df[df.format_rules != "opinion_actu"]
    results = {
        "snapshot": SNAPSHOT.isoformat(),
        "channel": {"handle": "@Finary", "subscribers_label": "917 k", "uploads_label": "975 vidéos (dont Shorts)"},
        "overview": {
            "n_long": int(len(df)), "n_compared": int(len(comp)),
            "total_views_long": int(df.views.sum()),
            "median_views_all": int(df.views.median()),
            "median_views_last12": int(last12[last12.cohort != "moins de 1 mois"].views.median()),
            "n_last12": int(len(last12)),
            "uploads_per_month_last12": r2(len(last12) / 12),
        },
        "shorts": {"n": int(len(shorts)), "median_views": int(shorts.views.median()),
                   "p25": int(shorts.views.quantile(.25)), "p75": int(shorts.views.quantile(.75)),
                   "max": int(shorts.views.max()),
                   "share_pointing_to_long": r2(shorts.title.str.contains("vidéo compl|sur la chaîne|enquête complète", case=False).mean())},
        "trend": trend,
        "by_format": group_stats(comp, "format", FORMAT_LABEL),
        "by_theme": group_stats(comp, "theme", THEME_LABEL),
        "format_mix": mix,
        "durations": durations,
        "title_features": feats,
        "format_effects_vs_analyse": format_effects,
        "matrix": matrix,
        "intent": intent,
        "reco": reco,
        "analyse_label": serie,
        "top": json.loads(top.round({"perf_index": 2}).to_json(orient="records", force_ascii=False)),
        "bottom": json.loads(bottom_formats.round({"perf_index": 2}).to_json(orient="records", force_ascii=False)),
        "labels_check": {
            "agreement_all": r2((df.format == df.format_rules).mean()),
            "n_rules_decided": int(len(rules_decided)),
            "agreement_when_rules_decide": r2((rules_decided.format == rules_decided.format_rules).mean()),
        },
    }
    (ROOT / "analysis" / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    # version allégée pour le tableau de bord (toutes les vidéos, colonnes utiles)
    slim = df[cols + ["age_label"]].copy()
    slim["perf_index"] = slim.perf_index.round(2)
    (ROOT / "docs" / "data.json").write_text(json.dumps({"results": results,
        "videos": json.loads(slim.to_json(orient="records", force_ascii=False))}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: results[k] for k in ["overview", "shorts", "labels_check", "analyse_label"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
