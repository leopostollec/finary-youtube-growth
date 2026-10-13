"""Taxonomie des vidéos (format et thème) + classifieur à règles utilisé comme contrôle.

Les étiquettes de référence viennent d'un LLM (voir agent/prompts/classify.md).
Le classifieur à règles ci-dessous est volontairement simple et indépendant :
il sert à mesurer l'accord avec le LLM, pas à le remplacer.
"""
import re

FORMATS = {
    "A": ("analyse_patrimoine", "Analyse de patrimoine"),
    "T": ("talk_expert", "Interview d'expert"),
    "R": ("recit", "Récit / enquête"),
    "C": ("cours_guide", "Cours / guide"),
    "O": ("opinion_actu", "Opinion / actu"),
    "M": ("temoignage", "Témoignage"),
    "P": ("finary_produit", "Produit Finary"),
}

THEMES = {
    "B": ("bourse_etf", "Bourse & ETF"),
    "I": ("immobilier", "Immobilier"),
    "K": ("crypto", "Crypto"),
    "E": ("epargne_fire", "Épargne & FIRE"),
    "F": ("fiscalite_retraite", "Fiscalité & retraite"),
    "U": ("ultra_riches", "Ultra-riches"),
    "G": ("eco_geopolitique", "Économie & géopolitique"),
    "S": ("strategie_patrimoine", "Stratégie patrimoniale"),
    "P": ("finary", "Finary"),
    "X": ("autre", "Autre"),
}

FORMAT_LABEL = {slug: label for slug, label in FORMATS.values()}
THEME_LABEL = {slug: label for slug, label in THEMES.values()}

# Hypothèse (à valider avec les données d'inscription) : proximité du thème avec un produit Finary.
# « forte » = le spectateur peut agir tout de suite dans l'app (suivre son PEA, investir en ETF, en crypto…)
THEME_INTENT = {
    "bourse_etf": "forte",            # Finary Invest, suivi PEA / CTO
    "crypto": "forte",                # crypto dans Finary
    "strategie_patrimoine": "forte",  # agrégateur, score, Finary One
    "epargne_fire": "forte",          # budget, épargne, projection
    "fiscalite_retraite": "moyenne",  # assurance-vie (Finary Life), le reste moins
    "immobilier": "moyenne",          # suivi des biens, pas d'offre directe
    "ultra_riches": "faible",
    "eco_geopolitique": "faible",
    "autre": "faible",
    "finary": "produit",
}

_A = re.compile(r"analyse de patrimoine|pr[ée]sentation de (patrimoine|portefeuille)|analyse de cashflow|"
                r"j[’']analyse (son|le|ce) (patrimoine|plan)|analyse de 3 profils|analyse ultra|"
                r"j[’']analyse le patrimoine|son patrimoine !|analyser le patrimoine", re.I)
_T = re.compile(r"finary talk|talk #|\(avec |avec @|\bft\.|l[’']avis d[’']un expert|pr[ée]visions d[’']un expert|"
                r"d[’']un insider|ex-trader|banquier priv[ée]s?\)|\| [A-ZÉ][\w’'-]+ [A-ZÉ][\w’'-]+|- (marc touati|charles gave)", re.I)
_P = re.compile(r"\bfinary\b|predict :|community call", re.I)
_R = re.compile(r"l[’']art de|l[’']histoire|la vie \(folle\)|saga|dynastie|qu[’']arrive-t-il|le pays|"
                r"l[’']entreprise|la banque qui|une vie$|personne ne parle|que vous ne connaissez pas|"
                r"(famille|clan) .*(riche|secret)|milliardaires? |à quoi ressemble .*(milliards|infini|famille)|enqu[êe]te", re.I)
_C = re.compile(r"guide|cours|\btop \d|tout comprendre|expliqu|comment investir|faut-il|mes \d|le[çc]ons|"
                r"erreurs? à éviter|\d+ minutes|ou s&p|r[èe]gles d[’']or|le secret|le plan|m[ée]thodes", re.I)
_M = re.compile(r"il explique comment|à quoi ressembl|elle [ée]pargne|^à \d+ ans, il|il a regard|comment ils vivent|"
                r"de 0 à millionnaire|m[ée]decin millionnaire", re.I)


def rule_format(title: str) -> str:
    """Classifieur de contrôle : renvoie un slug de format."""
    t = title.strip()
    if _A.search(t):
        return "analyse_patrimoine"
    if _T.search(t):
        return "talk_expert"
    if _P.search(t):
        return "finary_produit"
    if _M.search(t):
        return "temoignage"
    if _R.search(t):
        return "recit"
    if _C.search(t):
        return "cours_guide"
    return "opinion_actu"


# ---- motifs de titres (variables explicatives) ---------------------------------------------

_ACRONYMS = {"MSCI", "SCPI", "LMNP", "PEA", "ETF", "CAC", "GAFAM", "BRICS", "CRS", "CEO", "NVIDIA", "PER", "CTO",
             "DCA", "FIRE", "BMW", "LVMH", "XRP", "DAO", "VIE", "SMIC", "NASDAQ", "CGP", "LE", "AU", "DE", "ON", "IA",
             "USA", "PREMIER", "SIMULATEUR", "PATRIMOINE", "MONDE"}

TITLE_FEATURES = {
    "montant_euros": ("Montant en € dans le titre", re.compile(r"\d[\d\s  .,]*\s?(k|m|M|Mds|millions?|milliards?)?\s?(€|euros?)|€\s?\d|\d\s?(k€|M€|m€)", re.I)),
    "question": ("Titre en question", re.compile(r"\?")),
    "personnage": ("Un personnage (il / elle / ce…)", re.compile(r"^(il|elle|ils|cet?|cette|son|sa|ses)\b|\b(il|elle) (a|est|vise|gagne|épargne|investit|perd|hérite|débute|vend|revend|raconte)\b", re.I)),
    "riche": ("Richesse / milliardaires", re.compile(r"riche|richesse|milliard|millionnaire|fortune|ultra-riches", re.I)),
    "secret": ("Secret / caché", re.compile(r"secr[eè]t|personne ne parle|que vous ne connaissez pas|ce que cache|que cache|confidentiel", re.I)),
    "vous": ("S'adresse au spectateur (vous)", re.compile(r"\b(vous|votre|vos)\b", re.I)),
    "je": ("L'hôte parle (je / mon)", re.compile(r"\b(je|j[’']|mon|mes|ma)\b", re.I)),
    "majuscules": ("Un mot en MAJUSCULES", None),
    "superlatif": ("Superlatif (le plus…)", re.compile(r"\b(le|la|les) plus\b|\bmeilleur", re.I)),
    "invite": ("Invité nommé", re.compile(r"\|\s*[A-ZÉ][\w’'-]+ [A-ZÉ]|\(avec |avec @|\bft\.|- (Marc Touati|Charles Gave|Sam Altman)|\(Marc Fiorentino\)", re.I)),
    "libelle_serie": ("Libellé de série (« | Analyse de patrimoine »…)", re.compile(r"(analyse de patrimoine|pr[ée]sentation de (patrimoine|portefeuille)|analyse de cashflow|finary talk|talk #\d+|fin[’']actu)", re.I)),
}


def has_caps_word(title: str) -> bool:
    for w in re.findall(r"[A-ZÀ-ÖØ-Þ]{4,}", title):
        if w not in _ACRONYMS:
            return True
    return False


def title_features(title: str) -> dict:
    out = {}
    for key, (_label, rx) in TITLE_FEATURES.items():
        if key == "majuscules":
            out[key] = has_caps_word(title)
        else:
            out[key] = bool(rx.search(title))
    return out
