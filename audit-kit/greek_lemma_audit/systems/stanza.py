"""``stanza-perseus`` / ``stanza-proiel`` systems (Stanza 1.14, ``grc`` packages).

Mirrors ``galen-density-map/pipeline/h3m/m2_agreement.py``: processors
``tokenize,pos,lemma``; output cached per work as JSONL
(``stanza_<package>/<stem>.jsonl``). Two sources, in order:

1. a cache directory (default: the project's ``data/qc/h3m/cache``), read-only;
2. the model itself, **only if already downloaded** under the Stanza resources
   dir (``STANZA_RESOURCES_DIR`` or ``~/stanza_resources``). The kit never
   downloads models unless ``allow_download=True`` is passed explicitly.

Fresh output is written to the kit's own cache dir (under ``--out``), never to
the project cache.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..corpus import Token, Work
from .base import Availability, System, exc_text

PROCESSORS = "tokenize,pos,lemma"


def stanza_resources_dir() -> Path:
    env = os.environ.get("STANZA_RESOURCES_DIR")
    return Path(env) if env else Path.home() / "stanza_resources"


def model_present(package: str, resources: Path | None = None) -> bool:
    res = resources or stanza_resources_dir()
    grc = res / "grc"
    if not grc.exists():
        return False
    # Stanza stores e.g. grc/tokenize/perseus.pt, grc/pos/perseus_charlm.pt, grc/lemma/perseus_*.pt
    for proc in ("tokenize", "lemma"):
        d = grc / proc
        if not d.exists() or not any(p.name.startswith(package) for p in d.glob("*.pt")):
            return False
    return True


class StanzaSystem(System):
    kind = "neural"

    def __init__(
        self,
        package: str,
        cache_dirs: list[Path] | None = None,
        write_cache_dir: Path | None = None,
        allow_download: bool = False,
    ) -> None:
        super().__init__()
        self.package = package
        self.name = f"stanza-{package}"
        self.cache_dirs = [Path(c) for c in (cache_dirs or [])]
        self.write_cache_dir = Path(write_cache_dir) if write_cache_dir else None
        self.allow_download = allow_download
        self._nlp = None
        self._model_ok: bool | None = None

    # -- availability ---------------------------------------------------------
    def _cached_path(self, stem: str) -> Path | None:
        for d in self.cache_dirs + ([self.write_cache_dir] if self.write_cache_dir else []):
            p = d / f"stanza_{self.package}" / f"{stem}.jsonl"
            if p.exists():
                return p
        return None

    def _n_cached(self) -> int:
        n = 0
        for d in self.cache_dirs:
            p = d / f"stanza_{self.package}"
            if p.exists():
                n += sum(1 for _ in p.glob("*.jsonl"))
        return n

    def probe(self) -> Availability:
        n_cached = self._n_cached()
        try:
            import stanza
        except Exception as exc:
            if n_cached:
                return Availability(True, f"stanza not importable ({exc_text(exc)}); using {n_cached} cached works only",
                                    {"stanza": None, "package": self.package, "cached_works": n_cached, "mode": "cache_only"})
            return Availability(False, f"stanza import failed: {exc_text(exc)}")
        version = getattr(stanza, "__version__", "unknown")
        present = model_present(self.package)
        self._model_ok = present or self.allow_download
        info = {"stanza": version, "package": self.package, "processors": PROCESSORS,
                "cached_works": n_cached, "model_downloaded": present,
                "resources_dir": str(stanza_resources_dir())}
        if present:
            return Availability(True, f"stanza {version}, grc/{self.package} model present; {n_cached} cached works", {**info, "mode": "model+cache"})
        if self.allow_download:
            return Availability(True, f"stanza {version}; grc/{self.package} will be downloaded on first use (allow_download)", {**info, "mode": "download"})
        if n_cached:
            return Availability(True, f"stanza {version} importable but grc/{self.package} model not downloaded; "
                                      f"using {n_cached} cached works only (pass --allow-download to fetch the model)",
                                {**info, "mode": "cache_only"})
        return Availability(False, f"stanza {version} importable but grc/{self.package} model not downloaded and no cache "
                                   f"(run stanza.download('grc', package='{self.package}') or pass --allow-download)", info)

    # -- running --------------------------------------------------------------
    def _load(self) -> Any:
        if self._nlp is None:
            import stanza

            kwargs: dict[str, Any] = dict(lang="grc", package=self.package, processors=PROCESSORS,
                                          verbose=False, tokenize_no_ssplit=False)
            if self.allow_download:
                stanza.download("grc", package=self.package, verbose=False)
            else:
                kwargs["download_method"] = None
            self._nlp = stanza.Pipeline(**kwargs)
        return self._nlp

    @staticmethod
    def _read_cache(path: Path) -> list[Token]:
        out: list[Token] = []
        with path.open(encoding="utf-8") as fh:
            for n, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                out.append(Token(i=int(row.get("i", n)), surface=row.get("surface") or "",
                                 lemma=row.get("lemma") or "", pos=row.get("pos") or row.get("upos") or ""))
        return out

    def run(self, work: Work) -> list[Token] | None:
        cached = self._cached_path(work.stem)
        if cached is not None:
            return self._read_cache(cached)
        if not self._model_ok:
            self.last_skip_reason = f"no cached output for {work.stem} and grc/{self.package} model not downloaded"
            return None
        try:
            nlp = self._load()
        except Exception as exc:
            self.last_skip_reason = f"pipeline load failed: {exc_text(exc)}"
            self._model_ok = False
            return None
        doc = nlp(work.running_text())
        out: list[Token] = []
        for sent in doc.sentences:
            for w in sent.words:
                if not (w.text or "").strip():
                    continue
                out.append(Token(i=len(out), surface=w.text, lemma=w.lemma or "", pos=w.upos or ""))
        if self.write_cache_dir is not None:
            p = self.write_cache_dir / f"stanza_{self.package}" / f"{work.stem}.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as fh:
                for t in out:
                    fh.write(json.dumps({"i": t.i, "surface": t.surface, "lemma": t.lemma, "pos": t.pos}, ensure_ascii=False) + "\n")
        return out
