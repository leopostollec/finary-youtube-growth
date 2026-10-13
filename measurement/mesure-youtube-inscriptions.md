# Mesurer ce que YouTube rapporte en inscriptions

L'analyse publique montre ce qui fait des **vues**. La décision qui compte (quels formats produire) dépend des **inscriptions** et des **abonnements payants** que chaque vidéo apporte. Ce plan décrit comment les mesurer avec ce que Finary a déjà (YouTube Studio, l'app, un outil d'analytics produit), en une à deux semaines de mise en place.

## 1. La métrique

> **Inscriptions pour 1 000 vues**, par vidéo, puis par format et par thème, à 28 jours après publication.
> Et en second niveau : **passages à l'offre payante pour 1 000 vues**, à 30 jours après l'inscription.

Pourquoi pour 1 000 vues : une vidéo à 2 M de vues et une à 90 k ne se comparent pas en volume d'inscriptions, mais en rendement.

## 2. Trois sources, du plus précis au plus complet

Aucune ne suffit seule : la plupart des spectateurs ne cliquent pas sur un lien, ils tapent « Finary » plus tard. On les combine.

| Source | Ce qu'elle capte | Mise en place |
|---|---|---|
| **Liens suivis** | les clics depuis la vidéo | un lien UTM par vidéo et par emplacement (description, commentaire épinglé, fiche, écran de fin) + un lien court dit à l'oral (`finary.com/yt/<mot>`) |
| **Déclaratif** | ceux qui ont vu sans cliquer | à l'inscription : « Comment as-tu connu Finary ? » → YouTube → « Quelle vidéo ? » (texte libre, normalisé par un LLM vers un identifiant de vidéo ou un thème) |
| **Modèle** | l'effet global d'une sortie | inscriptions par jour expliquées par les vues par jour des vidéos (API YouTube Analytics) et la saisonnalité ; donne un ordre de grandeur pour les vidéos sans clics |

Convention UTM (générée automatiquement par l'agent pour chaque nouvelle vidéo) :

```
utm_source=youtube
utm_medium=video
utm_campaign=<video_id>            ex. UaTXSbZdMrc
utm_content=<emplacement>          description | epingle | fiche | ecran_fin | oral
```

Aucune donnée personnelle dans les liens. Le déclaratif est facultatif et n'est exploité qu'en agrégé.

## 3. Modèle de données

```
youtube_videos (video_id, published_at, title, format, theme, duration_min)   -- agent/youtube_api.py + étiquettes LLM
youtube_daily  (video_id, day, views, watch_time_min)                          -- API YouTube Analytics
signups        (user_id, created_at, utm_source, utm_campaign, utm_content,
                self_reported_source, self_reported_video_id)                  -- app
subscriptions  (user_id, started_at, plan)                                     -- app / facturation
```

## 4. Attribution

Pour chaque inscription, une seule vidéo, dans cet ordre :

1. **lien suivi** cliqué dans les 30 jours précédant l'inscription (dernier clic) ;
2. sinon **déclaratif** normalisé ;
3. sinon : non attribuée à une vidéo (elle compte dans le modèle global).

On publie les trois chiffres côte à côte (liens / déclaratif / modèle) plutôt qu'un seul total qui cacherait l'incertitude.

## 5. Requêtes

Inscriptions pour 1 000 vues à 28 jours, par format (liens + déclaratif) :

```sql
with attributed as (
  select coalesce(s.utm_campaign, s.self_reported_video_id) as video_id, s.user_id, s.created_at
  from signups s
  where (s.utm_source = 'youtube' or s.self_reported_source = 'youtube')
    and coalesce(s.utm_campaign, s.self_reported_video_id) is not null
),
per_video as (
  select v.video_id, v.format, v.theme,
         (select sum(d.views) from youtube_daily d
           where d.video_id = v.video_id and d.day < v.published_at::date + 28) as views_28d,
         (select count(*) from attributed a
           where a.video_id = v.video_id and a.created_at < v.published_at + interval '28 days') as signups_28d
  from youtube_videos v
  where v.published_at < now() - interval '28 days'
)
select format,
       count(*)                                         as videos,
       sum(views_28d)                                   as views,
       sum(signups_28d)                                 as signups,
       round(1000.0 * sum(signups_28d) / nullif(sum(views_28d), 0), 2) as signups_per_1000_views
from per_video
group by format
order by signups_per_1000_views desc;
```

Passage à l'offre payante à 30 jours selon le thème de la vidéo d'acquisition :

```sql
select v.theme,
       count(distinct s.user_id)                                         as signups,
       count(distinct p.user_id)                                         as paid_30d,
       round(100.0 * count(distinct p.user_id) / count(distinct s.user_id), 1) as pct_paid_30d
from signups s
join youtube_videos v on v.video_id = coalesce(s.utm_campaign, s.self_reported_video_id)
left join subscriptions p on p.user_id = s.user_id
                         and p.started_at < s.created_at + interval '30 days'
group by v.theme
order by pct_paid_30d desc;
```

## 6. Le tableau de bord

Une page, mise à jour chaque lundi par l'agent :

- **En tête** : inscriptions venues de YouTube sur 7 jours, inscriptions pour 1 000 vues, part attribuée à une vidéo précise.
- **Par format et par thème** : vues, inscriptions pour 1 000 vues, passage payant à 30 jours (barres, une couleur par mesure, jamais deux échelles sur un même graphique).
- **Par vidéo** : tableau trié par inscriptions pour 1 000 vues, avec l'indice de performance en vues à côté : on voit d'un coup d'œil les vidéos « petites en vues, fortes en inscriptions ».
- **Cohortes** : rétention à 30 / 90 jours des inscrits, selon le thème de la vidéo d'acquisition.

## 7. Les décisions que ça débloque

| Test | Décision |
|---|---|
| 1. Inscriptions pour 1 000 vues par format | Si une analyse de patrimoine rapporte au moins 2,5 fois plus qu'un récit, on garde sa place au calendrier ; sinon on poursuit le virage vers les récits et les cours. |
| 2. Analyses racontées comme des récits | Si l'indice à 28 jours monte sans baisse des inscriptions pour 1 000 vues, on généralise le nouvel angle. |
| 3. Accueil par thème de vidéo | Si les comptes connectés à 7 jours et le passage payant à 30 jours montent face au groupe témoin, on étend à tous les thèmes. |

## 8. Limites

- Le déclaratif est approximatif (mémoire, vidéo regardée il y a longtemps) : il sert à départager, pas à compter au centime.
- Le dernier clic sous-estime les vidéos qui donnent envie sans faire cliquer, d'où le modèle global en parallèle.
- 28 jours ne capturent pas les vidéos « de fond » (guides, cours) qui convertissent pendant des mois : on regarde aussi le cumul à 180 jours.
