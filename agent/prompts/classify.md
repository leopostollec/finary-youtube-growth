Tu classes des vidéos YouTube d'une chaîne française d'éducation financière (Finary).
Pour chaque titre, choisis UN format et UN thème dans les listes ci-dessous, à partir du titre et de la durée.

## Formats
- analyse_patrimoine : l'hôte (ou un expert) analyse le patrimoine ou le plan d'une personne précise, abonné ou personnalité. Indices : « Analyse de patrimoine », « Présentation de portefeuille », « J'analyse son patrimoine », un métier + un âge + un montant.
- talk_expert : interview d'un invité expert ou d'un créateur (« Finary Talk », « | Prénom Nom », « avec @… », « l'avis d'un expert »). Souvent plus de 40 minutes.
- recit : récit ou enquête sur une personne riche, une famille, une entreprise, un pays ou un épisode historique (« L'art de… », « L'histoire secrète… », « Qu'arrive-t-il au Japon ? »).
- cours_guide : contenu pédagogique de l'hôte : guide, cours, top, comparaison, explication d'un produit financier (« PEA : le guide complet », « Ce cours sur … devrait être obligatoire », « MSCI World ou S&P500 ? »).
- opinion_actu : avis de l'hôte sur l'actualité, les marchés ou la société, revue d'actualité, expérience personnelle de l'hôte.
- temoignage : portrait d'une personne ordinaire qui raconte son parcours (« Elle épargne 63 % de son salaire… », « 1M€ à 25 ans : il explique comment il a fait »), sans analyse critique de son patrimoine.
- finary_produit : vidéo sur Finary elle-même (démo, fonctionnalité, annonce, levée de fonds, communauté).

## Thèmes
- bourse_etf : actions, ETF, PEA, CTO, dividendes, marchés, or, obligations, produits structurés.
- immobilier : immobilier locatif, résidence principale, SCPI, LMNP, Pinel, parkings.
- crypto : bitcoin, cryptos, stablecoins, DeFi.
- epargne_fire : taux d'épargne, budget, consommation, indépendance financière / retraite anticipée.
- fiscalite_retraite : impôts, assurance-vie, PER, retraite, transmission, holding, statut.
- ultra_riches : milliardaires, dynasties, personnalités et leur fortune, luxe.
- eco_geopolitique : économie, pays, crises, géopolitique, histoire et stratégie des entreprises, IA.
- strategie_patrimoine : construire son patrimoine en général, devenir riche, investir une somme, plusieurs classes d'actifs.
- finary : Finary, ses produits, sa communauté.
- autre : montres, art, cartes Pokémon, automobile, développement personnel…

## Règles
- Le format décrit la forme de la vidéo, le thème décrit son sujet principal.
- Pour une analyse de patrimoine, prends le thème mis en avant par le titre (« 10 appartements » → immobilier) ; sinon strategie_patrimoine.
- En cas de doute entre deux formats, choisis celui qui décrit le mieux ce que verra le spectateur.

## Réponse
Réponds uniquement en JSON, une entrée par vidéo, dans l'ordre reçu :
[{"id": "<video_id>", "format": "<format>", "theme": "<theme>"}]

## Exemples
- « Mon top 7 des ETF PEA pour 2026 ! » (19 min) → cours_guide, bourse_etf
- « 29 ans : il a 10 appartements et gagne 57 772 €/an avec ses loyers - Analyse de patrimoine » → analyse_patrimoine, immobilier
- « L'art de créer une dynastie légendaire : L'histoire secrète des Rothschild » → recit, ultra_riches
- « Où investir en 2026 : or, énergie, IA - Charles Gave » (57 min) → talk_expert, bourse_etf
