"""
RMRB_Dataset_v6
===============
Turns the raw RMRB advertisement archive (`{DATA_ROOT}/{YEAR}_AD/{YYYYMMDD}/*.json`)
into the daily panel data the factor / backtest layers consume.

Why this module exists
----------------------
`AD-Quant-Analysis.ipynb` and `Industry-Analysis.ipynb` both start from a single
pre-baked file, `AD_Industry_Count_Analysis.csv`, which collapses every ad into
"one hard count for the top-2 modal industries, commercial ads only". That throws
away four things the raw archive actually carries, and each of them has an
economic interpretation:

1. **Ad size.** A full-page (FAD) ad costs several times a half-page block. Size
   is the closest thing we have to *ad spend*, and spend — not headline count —
   is what a sector's marketing budget actually reveals.
2. **Page prominence.** Page 1-4 of the People's Daily is political real estate;
   page 16 is not. Prominence proxies editorial priority.
3. **Model disagreement.** Every ad is classified by many LLMs. Taking the modal
   label discards the confidence information. An ad that 15/15 models call
   `房地产` is a cleaner observation than one split 8/7.
4. **Ad type.** Commercial ads (corporates buying space) and public-service /
   policy ads (the propaganda agenda) are *different economic signals* and must
   not be pooled. The legacy pipeline simply dropped the policy ads.

Output panels (all daily, calendar-day indexed, industries as columns)
---------------------------------------------------------------------
    count_commercial      soft-voted commercial ad count per SW L1 industry
    count_public          soft-voted public-service / policy ad count
    count_all             every retained ad regardless of type
    area_commercial       commercial ads weighted by page-area (1.0 = full page)
    area_public           public-service ads weighted by page-area
    prominence_commercial commercial ads weighted by page-area x front-page bonus
    count_legacy          hard top-2 modal count, reproduces the legacy CSV

plus a `macro` frame of market-wide daily series (total ads, total area,
commercial share, mean page, model coverage).

Usage
-----
    from RMRBCore.RMRB_Dataset_v6 import RMRBDataset
    ds = RMRBDataset()                 # auto-resolves the data root
    panels = ds.build_panels()         # cached; pass rebuild=True to force
    market = ds.load_market()          # SW L1 industry + benchmark returns
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")

#: Candidate data roots, tried in order. A valid root holds `{YEAR}_AD/` folders.
_DATA_ROOT_CANDIDATES = (
    os.environ.get("RMRB_DATA_ROOT", ""),
    f"{_REPO_ROOT}/RMRBData/RMRBData/",
    f"{_REPO_ROOT}/RMRBData/",
)


def _looks_like_data_root(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    return any(re.fullmatch(r"\d{4}_AD", name) for name in os.listdir(path))


def resolve_data_root(explicit: str = "") -> str:
    """Locate the RMRB archive root.

    Search order: explicit argument, ``RMRB_DATA_ROOT`` env var, the in-repo
    ``RMRBData/`` folder, then the drive list in ``Config/Config.py``. The data
    itself is deliberately never committed, so this has to be tolerant.
    """
    candidates = [explicit, *_DATA_ROOT_CANDIDATES]
    try:  # Config is optional — the module must import on a bare checkout.
        from Config.Config import EXTERNAL_PATH_LIST

        candidates.extend(EXTERNAL_PATH_LIST)
    except Exception:
        pass

    for candidate in candidates:
        if not candidate:
            continue
        path = candidate.replace("\\", "/").rstrip("/") + "/"
        if _looks_like_data_root(path):
            return path

    raise FileNotFoundError(
        "Could not locate the RMRB data root. Set RMRB_DATA_ROOT to the folder "
        "that contains the `{YEAR}_AD/` directories, or place it at "
        f"{_REPO_ROOT}/RMRBData/."
    )


# ---------------------------------------------------------------------------
# Label normalisation
# ---------------------------------------------------------------------------

#: The 31 Shenwan level-1 industries. Loaded from the mapping file when present;
#: this literal is the fallback so the module stays importable without data.
SW_LEVEL1_FALLBACK = [
    "农林牧渔", "基础化工", "钢铁", "有色金属", "电子", "汽车", "家用电器",
    "食品饮料", "纺织服饰", "轻工制造", "医药生物", "公用事业", "交通运输",
    "房地产", "商贸零售", "社会服务", "银行", "非银金融", "综合", "建筑材料",
    "建筑装饰", "电力设备", "机械设备", "国防军工", "计算机", "传媒", "通信",
    "煤炭", "石油石化", "环保", "美容护理",
]

#: Common LLM spellings that do not match the official Shenwan level-1 names.
_INDUSTRY_ALIASES = {
    "食品饮料Ⅱ": "食品饮料",
    "商业贸易": "商贸零售",
    "休闲服务": "社会服务",
    "化工": "基础化工",
    "纺织服装": "纺织服饰",
    "采掘": "煤炭",
    "电气设备": "电力设备",
    "建筑": "建筑装饰",
    "餐饮旅游": "社会服务",
    "信息服务": "计算机",
    "交运设备": "汽车",
    "黑色金属": "钢铁",
    "金融服务": "非银金融",
    "房地产业": "房地产",
    "美容护理Ⅱ": "美容护理",
}

AD_TYPE_COMMERCIAL = "commercial"
AD_TYPE_PUBLIC = "public"
AD_TYPE_OTHER = "other"


def normalise_ad_type(raw: str) -> str:
    """Map one model's free-text ``ad_type`` onto {commercial, public, other}.

    The LLMs mostly answer 商业广告 / 公益广告 but produce a long tail of hybrids
    ("商业广告（带有政府宣传性质）", "政务/公益广告", ...). Commercial intent wins
    ties: a hybrid ad still involved a corporate media buy, which is the thing
    the commercial-spend hypothesis is about.
    """
    if not raw:
        return AD_TYPE_OTHER
    text = str(raw)
    if "商业" in text or "企业形象" in text or "招商" in text:
        return AD_TYPE_COMMERCIAL
    if "公益" in text or "政策" in text or "政务" in text or "政治" in text:
        return AD_TYPE_PUBLIC
    if "形象" in text or "宣传" in text or "政绩" in text:
        return AD_TYPE_PUBLIC
    return AD_TYPE_OTHER


def normalise_industry(raw: str, valid: set, level: int = 1) -> str:
    """Truncate an ``industry`` string to ``level`` Shenwan tiers and validate it.

    ``社会服务-旅游及景区-旅游综合`` becomes ``社会服务`` at level 1 and
    ``社会服务-旅游及景区`` at level 2. Known aliases are resolved on the level-1
    head. Returns "" when the result is not a tradable Shenwan index — going to
    level 2 roughly quadruples the cross-section, but only for the sub-industries
    that actually have a published index.
    """
    if not raw:
        return ""
    parts = [p.strip() for p in str(raw).split("-") if p.strip()]
    if not parts:
        return ""
    parts[0] = _INDUSTRY_ALIASES.get(parts[0], parts[0])
    if len(parts) < level:
        return ""
    name = "-".join(parts[:level])
    return name if name in valid else ""


# ---------------------------------------------------------------------------
# Ad-level record extraction
# ---------------------------------------------------------------------------

#: Filename shapes we retain. The archive uses two full-page conventions —
#: `YYYYMMDDPP_PP_FAD.json` (2014 batch) and `YYYYMMDD_PP_FAD.json` (2015 on) —
#: and extracted blocks are `YYYYMMDD_PP_{HAD,CV,FAD}_Block_{i}.json`, with the
#: page number sometimes unpadded.
_FAD_RE = re.compile(r"^(\d{8})(?:\d{2})?_(\d{1,2})_FAD$")
_BLOCK_RE = re.compile(r"^(\d{8})_(\d{1,2})_(FAD|HAD|CV)_Block_(\d+)$")

#: Blocks below this share of a page are furniture (mastheads, tiny notices),
#: not media buys worth counting.
_MIN_BLOCK_PAGE_SHARE = 0.02


@dataclass
class AdRecord:
    """One retained advertisement, after multi-model vote aggregation."""

    date: str                                   # YYYYMMDD
    name: str
    page: int
    unit: str                                   # FAD | HAD_Block | CV_Block
    area_pages: float                           # 1.0 == one full newspaper page
    n_models: int                               # models that classified this ad
    ocr_len: int
    p_commercial: float                         # share of models voting commercial
    p_public: float
    industry_soft: dict = field(default_factory=dict)   # L1 -> probability, sums to <=1
    industry_hard: list = field(default_factory=list)   # legacy top-2 modal labels
    industry_agreement: float = 0.0             # probability mass on the top L1


def _page_prominence(page: int) -> float:
    """Editorial weight of a page.

    Pages 1-4 of the People's Daily carry the leadership news and are the most
    expensive and most closely read; the back sections are commodity space. A
    mild 2x-to-1x ramp keeps the effect economically motivated without letting a
    single front-page ad dominate the panel.
    """
    if page <= 1:
        return 2.0
    if page <= 4:
        return 1.5
    if page <= 8:
        return 1.2
    return 1.0


def _parse_ad_json(payload: dict, valid_industries: set, ocr_model: str, level: int = 1):
    """Aggregate the ``Summary~provider~model~ocr~timestamp`` blocks of one file.

    Returns ``None`` when the ad has no usable OCR text (nothing was read off the
    page, so any classification is a hallucination) or no model votes.
    """
    ocr_text = payload.get(f"OCR_{ocr_model}", "")
    if not ocr_text:
        return None

    industry_mass = Counter()
    hard_industry_votes = []
    type_votes = Counter()
    n_models = 0

    for key, value in payload.items():
        if not key.startswith("Summary") or not isinstance(value, dict):
            continue
        n_models += 1

        # One model may name several industries; treat them as an equal-weight
        # set so a model that hedges across three sectors does not out-vote a
        # model that commits to one.
        model_labels = set()
        for chunk in str(value.get("industry", "")).split(","):
            label = normalise_industry(chunk, valid_industries, level)
            if label:
                model_labels.add(label)
        if model_labels:
            share = 1.0 / len(model_labels)
            for label in model_labels:
                industry_mass[label] += share
            hard_industry_votes.extend(model_labels)

        type_votes[normalise_ad_type(value.get("ad_type", ""))] += 1

    if n_models == 0:
        return None

    industry_soft = {k: v / n_models for k, v in industry_mass.items()}
    agreement = max(industry_soft.values()) if industry_soft else 0.0
    hard = [name for name, _ in Counter(hard_industry_votes).most_common(2)]

    return {
        "industry_soft": industry_soft,
        "industry_hard": hard,
        "industry_agreement": agreement,
        "p_commercial": type_votes[AD_TYPE_COMMERCIAL] / n_models,
        "p_public": type_votes[AD_TYPE_PUBLIC] / n_models,
        "n_models": n_models,
        "ocr_len": int(payload.get(f"OCR_{ocr_model}_Len", len(ocr_text)) or 0),
    }


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

PANEL_NAMES = (
    "count_commercial",
    "count_public",
    "count_all",
    "area_commercial",
    "area_public",
    "prominence_commercial",
    "count_legacy",
)


class RMRBDataset:
    """Reads the RMRB archive and the market data that sits beside it."""

    def __init__(
        self,
        data_root: str = "",
        ocr_model: str = "Paddeocr_V3",
        begin_year: int = 2014,
        end_year: int = 2025,
        cache_dir: str = "",
        level: int = 1,
    ):
        self.data_root = resolve_data_root(data_root)
        self.etf_path = self.data_root + "ETF-Data/"
        self.ocr_model = ocr_model
        self.begin_year = begin_year
        self.end_year = end_year
        self.level = level
        self.cache_dir = (cache_dir or self.data_root + "Factor-Data/").replace("\\", "/")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.industries = self._load_sw_industries(level)
        self.sw_level1 = self._load_sw_industries(1)
        self._valid_industries = set(self.industries)
        self.diagnostics: dict = {}

    # -- reference data ----------------------------------------------------

    def _load_sw_industries(self, level: int) -> list:
        """Shenwan index names at the requested tier, in mapping-file order."""
        mapping_file = self.etf_path + "SW-SECTOR-PATH-MAPPING.json"
        if os.path.isfile(mapping_file):
            with open(mapping_file, encoding="utf-8") as handle:
                mapping = json.load(handle)
            names = [name for name in mapping if name.count("-") == level - 1]
            if names:
                return names
        if level == 1:
            return list(SW_LEVEL1_FALLBACK)
        raise FileNotFoundError(
            "SW-SECTOR-PATH-MAPPING.json is required for level-2 industries."
        )

    def _load_shape_areas(self, year: int) -> dict:
        """``block name -> pixel area`` for one year, from the shape dictionary."""
        path = f"{self.data_root}{year}_AD/{year}_Shape_Dict.json"
        if not os.path.isfile(path):
            return {}
        with open(path, encoding="utf-8") as handle:
            shapes = json.load(handle)
        areas = {}
        for entry in shapes.values():
            block = entry.get("output_block_path", "")
            if not block:
                continue
            try:
                areas[os.path.splitext(block)[0]] = int(entry["w"]) * int(entry["h"])
            except (KeyError, TypeError, ValueError):
                continue
        return areas

    def _load_dedup_filter(self, year: int) -> set:
        """Block names that survived the duplicate/outlier screen for one year.

        The same creative runs for weeks at a time; without this screen a single
        campaign would look like a sustained attention shock.
        """
        path = f"{self.data_root}{year}_AD/{year}_Shape_Dict_Final_Filter_Outlier.json"
        if not os.path.isfile(path):
            return set()
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return {os.path.splitext(name)[0] for name in payload.get("Final_Filter", [])}

    # -- ad-level extraction ----------------------------------------------

    def iter_records(self):
        """Yield one :class:`AdRecord` per retained advertisement."""
        stats = Counter()

        for year in range(self.begin_year, self.end_year + 1):
            year_dir = f"{self.data_root}{year}_AD/"
            if not os.path.isdir(year_dir):
                continue

            keep_blocks = self._load_dedup_filter(year)
            areas_px = self._load_shape_areas(year)
            # Self-calibrating page size: the modal RMRB ad unit is the half
            # page, so twice the median block area is one page. Avoids hard-
            # coding a DPI that may change between scan batches.
            page_area_px = 2.0 * np.median(list(areas_px.values())) if areas_px else 1.0

            for day in sorted(os.listdir(year_dir)):
                day_dir = os.path.join(year_dir, day)
                if not os.path.isdir(day_dir) or not day.isdigit():
                    continue

                for filename in sorted(os.listdir(day_dir)):
                    if not filename.endswith(".json"):
                        continue
                    name = filename[:-5]

                    fad = _FAD_RE.match(name)
                    block = _BLOCK_RE.match(name)
                    if fad:
                        date, page, unit, area_pages = fad.group(1), int(fad.group(2)), "FAD", 1.0
                    elif block:
                        if name not in keep_blocks:
                            stats["dropped_duplicate_block"] += 1
                            continue
                        date, page = block.group(1), int(block.group(2))
                        unit = f"{block.group(3)}_Block"
                        area_pages = float(np.clip(areas_px.get(name, 0.0) / page_area_px, 0.0, 1.0))
                        if area_pages < _MIN_BLOCK_PAGE_SHARE:
                            stats["dropped_tiny_block"] += 1
                            continue
                    else:
                        stats["dropped_unparsed_name"] += 1
                        continue

                    try:
                        with open(os.path.join(day_dir, filename), encoding="utf-8") as handle:
                            payload = json.load(handle)
                    except (OSError, json.JSONDecodeError):
                        stats["dropped_unreadable"] += 1
                        continue

                    parsed = _parse_ad_json(
                        payload, self._valid_industries, self.ocr_model, self.level
                    )
                    if parsed is None:
                        stats["dropped_no_ocr_or_votes"] += 1
                        continue

                    stats["kept"] += 1
                    stats["kept_" + unit] += 1
                    yield AdRecord(
                        date=date, name=name, page=page, unit=unit,
                        area_pages=area_pages, **parsed,
                    )

        self.diagnostics["extraction"] = dict(stats)

    # -- panel construction ------------------------------------------------

    def build_panels(self, rebuild: bool = False, verbose: bool = True) -> dict:
        """Build (or load) every daily industry panel.

        Each ad contributes its industry probability vector, scaled by the
        panel's weighting scheme, to the day it was printed. Commercial and
        public-service intensity are split by the model vote share rather than a
        hard label, so a genuinely ambiguous ad lands partly in both panels
        instead of being forced into one.
        """
        cached = self._load_cached_panels()
        if cached is not None and not rebuild:
            if verbose:
                print(f">>> Loaded cached panels from {self.cache_dir}")
            return cached

        columns = self.industries
        col_index = {name: i for i, name in enumerate(columns)}
        rows: dict = {}          # date -> panel -> np.ndarray
        macro_rows: dict = {}    # date -> dict of scalars

        def blank():
            return {panel: np.zeros(len(columns)) for panel in PANEL_NAMES}

        for rec in self.iter_records():
            bucket = rows.setdefault(rec.date, blank())
            macro = macro_rows.setdefault(
                rec.date,
                {"n_ads": 0, "area_total": 0.0, "area_commercial": 0.0,
                 "ocr_len_total": 0, "page_sum": 0, "model_sum": 0, "agreement_sum": 0.0},
            )

            prominence = _page_prominence(rec.page)
            for industry, prob in rec.industry_soft.items():
                idx = col_index[industry]
                bucket["count_all"][idx] += prob
                bucket["count_commercial"][idx] += prob * rec.p_commercial
                bucket["count_public"][idx] += prob * rec.p_public
                bucket["area_commercial"][idx] += prob * rec.p_commercial * rec.area_pages
                bucket["area_public"][idx] += prob * rec.p_public * rec.area_pages
                bucket["prominence_commercial"][idx] += (
                    prob * rec.p_commercial * rec.area_pages * prominence
                )

            # Legacy reproduction: hard top-2 labels, commercial ads only, one
            # count per industry per ad. Kept so results can be diffed against
            # AD_Industry_Count_Analysis.csv.
            if rec.p_commercial >= 0.5:
                for industry in rec.industry_hard:
                    bucket["count_legacy"][col_index[industry]] += 1.0

            macro["n_ads"] += 1
            macro["area_total"] += rec.area_pages
            macro["area_commercial"] += rec.area_pages * rec.p_commercial
            macro["ocr_len_total"] += rec.ocr_len
            macro["page_sum"] += rec.page
            macro["model_sum"] += rec.n_models
            macro["agreement_sum"] += rec.industry_agreement

        if not rows:
            raise RuntimeError("No advertisements were extracted — check the data root.")

        index = pd.to_datetime(sorted(rows), format="%Y%m%d")
        full_index = pd.date_range(index.min(), index.max(), freq="D")

        panels = {}
        for panel in PANEL_NAMES:
            frame = pd.DataFrame(
                [rows[d.strftime("%Y%m%d")][panel] for d in index],
                index=index, columns=columns,
            )
            # Days with no paper (or no ads) are genuine zeros, not gaps.
            panels[panel] = frame.reindex(full_index, fill_value=0.0).rename_axis("date")

        macro = pd.DataFrame(
            [macro_rows[d.strftime("%Y%m%d")] for d in index], index=index,
        ).reindex(full_index, fill_value=0).rename_axis("date")
        macro["mean_page"] = (macro["page_sum"] / macro["n_ads"].replace(0, np.nan))
        macro["mean_models"] = (macro["model_sum"] / macro["n_ads"].replace(0, np.nan))
        macro["mean_agreement"] = (macro["agreement_sum"] / macro["n_ads"].replace(0, np.nan))
        macro["commercial_share"] = (
            macro["area_commercial"] / macro["area_total"].replace(0, np.nan)
        )
        panels["macro"] = macro

        self._save_panels(panels)
        if verbose:
            self.report_diagnostics(panels)
        return panels

    # -- caching -----------------------------------------------------------

    def _panel_file(self, panel: str) -> str:
        return f"{self.cache_dir}RMRB_Panel_L{self.level}_{panel}.csv"

    def _save_panels(self, panels: dict) -> None:
        for panel, frame in panels.items():
            frame.to_csv(self._panel_file(panel), encoding="utf-8")

    def _load_cached_panels(self):
        wanted = list(PANEL_NAMES) + ["macro"]
        if not all(os.path.isfile(self._panel_file(p)) for p in wanted):
            return None
        return {
            panel: pd.read_csv(self._panel_file(panel), parse_dates=["date"], index_col="date")
            for panel in wanted
        }

    # -- market data -------------------------------------------------------

    def load_market(self, begin: str = "20140201", end: str = "20251231",
                    level: int = None) -> dict:
        """Load SW industry returns (at the dataset's tier) and the index benchmarks.

        Returns are close-to-close on the true trading-day calendar taken from
        HS300. A suspended or not-yet-launched index contributes 0.0 for that
        day rather than propagating NaN through the portfolio maths.
        """
        with open(self.etf_path + "SW-SECTOR-PATH-MAPPING.json", encoding="utf-8") as handle:
            sector_paths = json.load(handle)
        with open(self.etf_path + "BENCHMARK-PATH-MAPPING.json", encoding="utf-8") as handle:
            benchmark_paths = json.load(handle)

        start_dt, end_dt = pd.to_datetime(begin), pd.to_datetime(end)

        calendar_file = benchmark_paths[list(benchmark_paths)[0]]
        calendar = pd.read_csv(self.etf_path + calendar_file, parse_dates=["date"])
        trading_days = pd.DatetimeIndex(
            calendar.loc[calendar["date"].between(start_dt, end_dt), "date"].sort_values().unique()
        )

        def series_for(file_name):
            frame = pd.read_csv(self.etf_path + file_name, parse_dates=["date"])
            frame = frame[frame["date"].between(start_dt, end_dt)].sort_values("date")
            if frame.empty:
                return pd.Series(0.0, index=trading_days)
            roi = frame["close"].pct_change()
            # First observed day: enter at the open, so book open-to-close.
            roi.iloc[0] = (frame["close"].iloc[0] - frame["open"].iloc[0]) / frame["open"].iloc[0]
            return pd.Series(roi.values, index=frame["date"]).reindex(trading_days, fill_value=0.0)

        level = self.level if level is None else level
        wanted = self._load_sw_industries(level)
        industry_roi = pd.DataFrame(
            {name: series_for(sector_paths[name]) for name in wanted if name in sector_paths},
            index=trading_days,
        ).rename_axis("date")
        benchmark_roi = pd.DataFrame(
            {name: series_for(path) for name, path in benchmark_paths.items()},
            index=trading_days,
        ).rename_axis("date")

        return {
            "trading_days": trading_days,
            "industry_roi": industry_roi,
            "benchmark_roi": benchmark_roi,
        }

    # -- reporting ---------------------------------------------------------

    def report_diagnostics(self, panels: dict) -> None:
        stats = self.diagnostics.get("extraction", {})
        macro = panels["macro"]
        active = macro[macro["n_ads"] > 0]
        print("\n" + "=" * 22 + " DATASET EXTRACTION " + "=" * 22)
        print(f"Data root          : {self.data_root}")
        print(f"Industry tier      : SW level {self.level} ({len(self.industries)} indices)")
        if stats:
            print(f"Ads retained       : {stats.get('kept', 0):,}")
            for unit in ("FAD", "HAD_Block", "CV_Block"):
                print(f"  {unit:<16}: {stats.get('kept_' + unit, 0):,}")
            for reason in ("dropped_duplicate_block", "dropped_tiny_block",
                           "dropped_no_ocr_or_votes", "dropped_unparsed_name",
                           "dropped_unreadable"):
                if stats.get(reason):
                    print(f"  {reason:<16}: {stats[reason]:,}")
        else:
            # Panels came from cache, so the per-file counters were never filled.
            print(f"Ads retained       : {int(macro['n_ads'].sum()):,} (from cached panels)")
        print(f"Publication days   : {len(active):,} of {len(macro):,} calendar days")
        print(f"Ads per active day : {active['n_ads'].mean():.2f}")
        print(f"Models per ad      : {active['mean_models'].mean():.1f}")
        print(f"Industry agreement : {active['mean_agreement'].mean():.1%}")
        print(f"Commercial share   : {active['commercial_share'].mean():.1%} of ad area")
        print(f"Cached to          : {self.cache_dir}")


if __name__ == "__main__":
    for tier in (1, 2):
        RMRBDataset(level=tier).build_panels(rebuild="--rebuild" in sys.argv)
