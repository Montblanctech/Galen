"""Author and work names for the LSJ-Gold tables: a hand list for the common ids, then the First1K catalog and the Perseus
manifest for everything else. Shared by score.py, leaderboard.py, coverage.py and paper_numbers.py."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

GDM = Path(__file__).resolve().parent.parent.parent
NAMES = {"tlg0085": "Aeschylus", "tlg0011": "Sophocles", "tlg0627": "Hippocrates", "tlg0086": "Aristotle", "tlg0057": "Galen", "tlg0031": "New Testament",
         "tlg0012": "Homer", "tlg0016": "Herodotus", "tlg0003": "Thucydides", "tlg0059": "Plato", "tlg0006": "Euripides", "tlg0019": "Aristophanes",
         "tlg0032": "Xenophon", "tlg0543": "Polybius", "tlg0099": "Strabo", "tlg0008": "Athenaeus", "tlg0001": "Apollonius Rhodius", "tlg0005": "Theocritus",
         "tlg0033": "Pindar", "tlg0014": "Demosthenes", "tlg0020": "Hesiod", "tlg0023": "Oppian", "tlg2045": "Nonnus", "tlg0526": "Josephus", "tlg0525": "Pausanias",
         "tlg0004": "Diogenes Laertius", "tlg0060": "Diodorus", "tlg0007": "Plutarch", "tlg0062": "Lucian", "tlg0010": "Isocrates", "tlg0028": "Antiphon",
         "tlg0540": "Lysias", "tlg1799": "Euclid", "tlg0551": "Appian", "tlg2046": "Quintus Smyrnaeus", "tlg0532": "Achilles Tatius", "tlg0554": "Chariton",
         "tlg0535": "Callistratus", "tlg0017": "Isaeus", "tlg0026": "Aeschines", "tlg0027": "Andocides", "tlg0030": "Hyperides", "tlg0029": "Dinarchus",
         "tlg0036": "Bion", "tlg0035": "Moschus", "tlg0548": "Apollodorus", "tlg0007a": "Plutarch", "tlg0093": "Theophrastus", "tlg0081": "Dionysius of Halicarnassus",
         "tlg0094": "Hippolytus", "tlg0541": "Menander", "tlg0545": "Aelian", "tlg0556": "Asclepiodotus", "tlg0557": "Epictetus", "tlg0561": "Longus", "tlg0562": "Marcus Aurelius",
         "tlg0641": "Xenophon of Ephesus", "tlg1389": "Harpocration", "tlg2003": "Julian", "tlg2200": "Libanius", "tlg4029": "Procopius", "tlg0018": "Philo", "tlg0096": "Aesop",
         "tlg0002": "Theognis", "tlg0013": "Homeric Hymns", "tlg0015": "Herodian", "tlg0022": "Nicander", "tlg0024": "Oppian of Apamea", "tlg0059a": "Plato",
         "tlg0612": "Lycophron", "tlg0613": "Demades", "tlg1735": "Aristides", "tlg0552": "Archimedes", "tlg0537": "Epicurus", "tlg0533": "Callimachus", "tlg0199": "Bacchylides",
         "tlg0096a": "Aesop", "tlg0732": "Aratus", "tlg0527": "Septuagint", "tlg0558": "Apollodorus Mechanicus", "tlg1304": "Cornutus"}


@lru_cache(maxsize=1)
def catalog_names() -> tuple[dict, dict]:
    """(author id -> group name, (author, work) -> work name) from the First1K catalog and the Perseus manifest."""
    author, work = {}, {}
    cat = GDM / "data" / "reference_corpus" / "_first1k_catalog.json"
    if cat.exists():
        for e in json.load(cat.open(encoding="utf-8")).get("catalog", []):
            m = re.match(r"urn:cts:greekLit:(tlg\d{4})\.(tlg\d{3})\.", e.get("urn", ""))
            if m:
                author.setdefault(m.group(1), e.get("group_name", ""))
                work.setdefault((m.group(1), m.group(2)), e.get("work_name", ""))
    man = GDM / "data" / "perseus_corpus" / "manifest.json"
    if man.exists():
        for e in json.load(man.open(encoding="utf-8")).get("works", []):
            a, w = e.get("author") or e.get("tlg_author"), e.get("work") or e.get("tlg_work")
            if a and w:
                if e.get("author_name") or e.get("group_name"):
                    author.setdefault(a, e.get("author_name") or e.get("group_name"))
                if e.get("title") or e.get("work_name"):
                    work.setdefault((a, w), e.get("title") or e.get("work_name"))
    return author, work


def author_name(a: str) -> str:
    if a in NAMES:
        return NAMES[a]
    return catalog_names()[0].get(a) or a


def work_name(a: str, w: str) -> str:
    return catalog_names()[1].get((a, w)) or w
