"""Tests de l'agent, sans réseau : python agent/test_agent.py"""
import json
from datetime import date

import weekly_report as wr

VIDEOS = [
    {"video_id": "AAAAAAAAAAA", "title": "Mon top 7 des ETF PEA pour 2026 !", "views": 500000, "age_days": 40, "duration_min": 19.5},
    {"video_id": "BBBBBBBBBBB", "title": "Il a 3 appartements à 29 ans - Analyse de patrimoine", "views": 60000, "age_days": 20, "duration_min": 28.0},
]


def test_llm_labels_are_used_and_validated():
    def fake_llm(_text):
        return 'Voici : [{"id": "AAAAAAAAAAA", "format": "cours_guide", "theme": "bourse_etf"},' \
               ' {"id": "BBBBBBBBBBB", "format": "inventé", "theme": "immobilier"}]'
    labels = wr.classify([dict(v) for v in VIDEOS], fake_llm)
    assert labels["AAAAAAAAAAA"] == ("cours_guide", "bourse_etf", "llm")
    # format hors taxonomie -> rejeté, repli sur les règles
    assert labels["BBBBBBBBBBB"][0] == "analyse_patrimoine" and labels["BBBBBBBBBBB"][2] == "règles"


def test_unreadable_llm_answer_falls_back_to_rules():
    labels = wr.classify([dict(v) for v in VIDEOS], lambda _t: "désolé, je ne peux pas")
    assert all(src == "règles" for _f, _t, src in labels.values())


def test_report_numbers_come_from_python():
    baseline, medians = wr.load_baseline()
    vids = [dict(v) for v in VIDEOS]
    labels = wr.classify(vids, None)
    report, slack = wr.build_report(vids, labels, medians, baseline, date(2026, 10, 13))
    idx_a = 500000 / medians["1 à 3 mois"]
    assert wr.fmt_x(idx_a) in report
    assert "Analyse de patrimoine" in report and "tester un titre « récit »" in report
    assert slack.startswith("Rapport YouTube : 2 vidéos")


def test_demo_runs_on_repository_data():
    baseline, medians = wr.load_baseline()
    vids = wr.demo_videos(baseline)
    assert len(vids) == 26
    report, _ = wr.build_report(vids, wr.classify(vids, None), medians, baseline, date(2026, 10, 13))
    assert report.count("\n| [") == 26


def test_iso_duration():
    from youtube_api import iso_minutes
    assert iso_minutes("PT1H2M3S") == 62.05 and iso_minutes("PT45S") == 0.75 and iso_minutes("P0D") == 0


if __name__ == "__main__":
    tests = [f for name, f in dict(globals()).items() if name.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(json.dumps({"tests": len(tests), "échecs": 0}))
