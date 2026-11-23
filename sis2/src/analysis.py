"""Summarize a ListenBrainz chart snapshot and render the report figures."""

from contextlib import closing
from pathlib import Path
import sqlite3

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import get_font_names
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter
import pandas as pd


KINDS = ("artist", "recording")
PERIODS = ("week", "month")
PERIOD_COLOR = {"week": "#2d6a94", "month": "#a95024"}
KIND_COLOR = {"artist": "#186866", "recording": "#784c93"}
INK = "#192a3a"
MUTED = "#506174"
GRID = "#dce4ec"
GROUP = ["kind", "period"]


def _name(row):
    return f"{row.track_name} · {row.artist_name}" if row.kind == "recording" else row.artist_name


def _shorten(label, limit=40):
    return label if len(label) <= limit else f"{label[:limit - 1].rstrip()}…"


def _figure(title, subtitle):
    figure = Figure(figsize=(11, 4.65), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    figure.suptitle(title, x=0.05, y=0.961, ha="left", color=INK, fontsize=20, fontweight="bold")
    figure.text(0.05, 0.869, subtitle, color=MUTED, fontsize=10)
    return figure


def _style_axis(axis, grid_axis):
    axis.set_facecolor("#f8fafc")
    axis.set_axisbelow(True)
    axis.grid(axis=grid_axis, color=GRID, linewidth=0.75)
    axis.tick_params(axis="both", colors=MUTED, length=0, labelsize=9, pad=7)
    for spine in axis.spines.values():
        spine.set_visible(False)


def _save(figure, path):
    figure.savefig(path, dpi=200)


def _leader_figure(frame, kind, path):
    is_artist = kind == "artist"
    title = "Leading artists by share of chart listens" if is_artist else "Leading recordings by listens per day"
    subtitle = (
        "First eight ranks in each chart · share of listens among its retained entries"
        if is_artist else
        "First eight ranks in each chart · listens divided by the length of the chart window"
    )
    figure = _figure(title, subtitle)
    axes = figure.subplots(1, 2, sharex=True, squeeze=False)[0]
    figure.subplots_adjust(left=0.18, right=0.97, bottom=0.14, top=0.76, wspace=0.62)
    kind_rows = frame.loc[frame["kind"].eq(kind) & frame["rank"].le(8)]
    field = "chart_share" if is_artist else "listens_per_day"
    max_value = float(kind_rows[field].max()) if len(kind_rows) else 1.0
    available_fonts = set(get_font_names())
    fonts = [font for font in ("DejaVu Sans", "Apple SD Gothic Neo", "Noto Sans CJK KR", "Nanum Gothic") if font in available_fonts]

    for axis, period in zip(axes, PERIODS):
        rows = kind_rows.loc[kind_rows["period"] == period]
        _style_axis(axis, "x")
        axis.set_title(period.title(), loc="left", color=PERIOD_COLOR[period], fontsize=13, fontweight="bold", pad=10)
        if rows.empty:
            axis.text(0.5, 0.5, "Chart unavailable", transform=axis.transAxes, ha="center", color=MUTED)
            axis.set_yticks([])
        else:
            labels = []
            for row in rows.itertuples(index=False):
                if is_artist:
                    labels.append(f"{row.rank}. {_shorten(row.artist_name, 21)}")
                else:
                    labels.append(f"{row.rank}. {_shorten(row.track_name, 21)}\n{_shorten(row.artist_name, 24)}")
            positions = range(len(rows))
            bars = axis.barh(positions, rows[field], height=0.53, color=PERIOD_COLOR[period])
            axis.set_yticks(positions, labels, fontsize=8.5, linespacing=0.92, fontfamily=fonts)
            axis.set_ylim(len(rows) - 0.5, -0.5)
            number_format = ".1%" if is_artist else ",.1f"
            axis.bar_label(bars, labels=[format(value, number_format) for value in rows[field]], color=INK, fontsize=8, padding=4)
        axis.set_xlim(0, max_value * 1.24)
        if is_artist:
            axis.xaxis.set_major_formatter(PercentFormatter(xmax=1))
            if max_value > 0.81:
                axis.set_xticks([0, 0.25, 0.5, 0.75, 1])
        else:
            decimals = 1 if max_value < 10 else 0
            axis.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=decimals == 0))
            axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.{decimals}f}"))
    _save(figure, path)


def _comparison_figure(frame, ranks, path):
    figure = _figure(
        "How the weekly and monthly charts compare",
        "Shares use each chart’s retained entries. Rank comparisons use each shared entity’s best rank.",
    )
    concentration, overlap = figure.subplots(1, 2)
    figure.subplots_adjust(left=0.09, right=0.955, bottom=0.235, top=0.75, wspace=0.34)
    rank_limit = max(10, int(frame["rank"].max())) if len(frame) else 100
    rank_ticks = [rank for rank in (1, 10, 25, 50, 75, 100) if rank <= rank_limit]

    _style_axis(concentration, "both")
    concentration.set_title("Cumulative share of chart listens", loc="left", color=INK, fontsize=12, fontweight="bold", pad=10)
    concentration.set(xlim=(1, rank_limit), ylim=(0, 1.02), xlabel="Rank cutoff")
    concentration.set_xticks(rank_ticks)
    concentration.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    concentration.axvline(10, color="#a3aeb9", linewidth=0.85)
    for (kind, period), rows in frame.groupby(GROUP, sort=False):
        concentration.plot(
            rows["rank"], rows["chart_share"].cumsum(),
            color=KIND_COLOR[kind], linestyle="-" if period == "week" else "--",
            linewidth=2, marker="o" if len(rows) == 1 else None,
            label=f"{kind.title()} · {period}",
        )
    if len(frame):
        concentration.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8, frameon=False, labelcolor=MUTED)

    _style_axis(overlap, "both")
    overlap.set_title("Rank of shared entries", loc="left", color=INK, fontsize=12, fontweight="bold", pad=10)
    overlap.set(xlim=(0, rank_limit * 1.03), ylim=(rank_limit * 1.03, 0), xlabel="Monthly rank", ylabel="Weekly rank")
    for setter in (overlap.set_xticks, overlap.set_yticks):
        setter([rank for rank in rank_ticks if rank != 10 or rank_limit < 25])
    overlap.plot([1, rank_limit], [1, rank_limit], color="#a3aeb9", linewidth=0.85, zorder=1)
    matched = ranks.dropna(subset=["week", "month"])
    for kind, rows in matched.groupby("kind", sort=False):
        overlap.scatter(
            rows["month"], rows["week"], color=KIND_COLOR[kind], alpha=0.72, s=24,
            marker="o" if kind == "artist" else "^", label=kind.title(), zorder=2,
        )
    if matched.empty:
        overlap.text(0.5, 0.5, "No shared entries", transform=overlap.transAxes, ha="center", color=MUTED)
    else:
        overlap.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8, frameon=False, labelcolor=MUTED)
    _save(figure, path)


def _window_stats(frame, csv_output):
    per_window = frame.groupby(GROUP, sort=False)
    summary = per_window.agg(
        rows=("rank", "size"), start_utc=("start_utc", "first"), end_utc=("end_utc", "first"),
        window_days=("window_days", "first"), total_listens=("listens", "sum"),
        median_listens=("listens", "median"), median_listens_per_day=("listens_per_day", "median"),
        distinct_artist_names=("artist_name", "nunique"), distinct_entities=("entity_key", "nunique"),
    )
    summary["top_10_share"] = (
        frame["chart_share"].where(frame["rank"] <= 10, 0).groupby([frame[column] for column in GROUP]).sum()
    )
    summary.to_csv(csv_output / "chart_summary.csv")

    numeric_fields = ["rank", "listens", "listens_per_day", "chart_share"]
    numeric = per_window[numeric_fields].describe()
    numeric.columns = [f"{field}_{stat}" for field, stat in numeric.columns]
    if numeric.empty:
        numeric = pd.DataFrame(columns=[*GROUP, *numeric.columns])
    else:
        numeric = numeric.reset_index()
    numeric.to_csv(csv_output / "numeric_summary.csv", index=False)

    categorical = []
    for (kind, period), rows in per_window:
        for field in ("kind", "period", "artist_name", "track_name", "entity_key"):
            values = rows[field].dropna()
            counts = values.value_counts()
            # Sort the names of any tied modes for a stable result across snapshots.
            top_frequency = int(counts.max()) if len(counts) else 0
            modes = sorted(counts[counts == top_frequency].index)
            categorical.append({
                "kind": kind, "period": period, "field": field,
                "non_null_count": len(values), "unique_count": len(counts),
                "most_frequent": modes[0] if modes else None,
                "frequency": top_frequency, "tied_modes": len(modes),
            })
    pd.DataFrame.from_records(categorical, columns=(
        "kind", "period", "field", "non_null_count", "unique_count", "most_frequent", "frequency", "tied_modes",
    )).to_csv(csv_output / "categorical_summary.csv", index=False)

    results = {}
    for (kind, period), row in summary.iterrows():
        leader = per_window.get_group((kind, period)).iloc[0]
        results[f"{kind}_{period}"] = {
            "rows": int(row["rows"]), "start_utc": str(row["start_utc"]), "end_utc": str(row["end_utc"]),
            "window_days": float(row["window_days"]), "total_listens": int(row["total_listens"]),
            "top_10_share": float(row["top_10_share"]), "median_listens": float(row["median_listens"]),
            "median_listens_per_day": float(row["median_listens_per_day"]),
            "distinct_artist_names": int(row["distinct_artist_names"]),
            "distinct_entities": int(row["distinct_entities"]),
            "leader": {
                "name": _name(leader), "rank": int(leader["rank"]), "listens": int(leader["listens"]),
                "listens_per_day": float(leader["listens_per_day"]), "chart_share": float(leader["chart_share"]),
            },
        }
    return results


def _rank_pivot(frame, csv_output):
    # Identifiers are comparable within a kind. Keep the best rank when an ID repeats in a list.
    keys = ["kind", "entity_key"]
    ranks = frame.pivot_table(index=keys, columns="period", values="rank", aggfunc="min")
    ranks = ranks.reindex(columns=PERIODS).rename_axis(columns=None).reset_index()
    ranks[list(PERIODS)] = ranks[list(PERIODS)].astype("Int64")
    labels = frame.drop_duplicates(keys).copy()
    labels["name"] = [_name(row) for row in labels.itertuples(index=False)]
    ranks = ranks.merge(labels[keys + ["name"]], on=keys, how="left", validate="one_to_one")
    ranks["rank_change"] = ranks["month"] - ranks["week"]
    ranks.to_csv(csv_output / "rank_comparison.csv", index=False)

    comparisons = {}
    for kind in KINDS:
        rows = ranks.loc[ranks["kind"] == kind]
        matched = rows.dropna(subset=["week", "month"])
        gains = matched.loc[matched["rank_change"] > 0].sort_values(["rank_change", "week"], ascending=[False, True])
        largest_gain = None
        if len(gains):
            gain = gains.iloc[0]
            largest_gain = {
                "name": str(gain["name"]), "positions": int(gain["rank_change"]),
                "week": int(gain["week"]), "month": int(gain["month"]),
            }
        both_windows_present = rows["week"].notna().any() and rows["month"].notna().any()
        comparisons[kind] = {
            "matched": len(matched), "week_only": int((rows["week"].notna() & rows["month"].isna()).sum()),
            "month_only": int((rows["month"].notna() & rows["week"].isna()).sum()), "union": len(rows),
            "jaccard": len(matched) / len(rows) if both_windows_present else None,
            "median_absolute_rank_change": float(matched["rank_change"].abs().median()) if len(matched) else None,
            "largest_weekly_gain": largest_gain,
        }
    return ranks, comparisons


def _captions(charts, comparisons):
    captions = {}
    for kind, filename in (("artist", "artists.png"), ("recording", "recordings.png")):
        results = []
        for period in PERIODS:
            chart = charts.get(f"{kind}_{period}")
            if chart is None:
                continue
            leader = chart["leader"]
            quantity = (
                f'{leader["chart_share"]:.1%} of listens among the retained chart entries'
                if kind == "artist" else f'{leader["listens_per_day"]:,.1f} listens per day'
            )
            results.append(f'{leader["name"]} led the {period} chart with {quantity}.')
        captions[filename] = " ".join(results) or f"No {kind} chart rows were available."

    results = []
    for kind, plural in (("artist", "artists"), ("recording", "recordings")):
        week = charts.get(f"{kind}_week")
        month = charts.get(f"{kind}_month")
        if week is None or month is None:
            continue
        matched = comparisons[kind]
        results.append(
            f'The first 10 ranks for {plural} captured {week["top_10_share"]:.1%} of the weekly chart and '
            f'{month["top_10_share"]:.1%} of the monthly chart. '
            f'{matched["matched"]} of {matched["union"]} distinct charted {plural} appeared in both lists.'
        )
    captions["cross_window.png"] = " ".join(results) or "Both windows are needed for a rank comparison."
    return captions


def analyze(db_path: Path, output: Path) -> dict:
    """Read the snapshot, export tables and figures, and return JSON-native report metrics."""
    with closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        frame = pd.read_sql_query(
            """SELECT kind, period, rank, artist_name, track_name, listens, entity_key,
                      start_utc, end_utc, listens_per_day
               FROM chart_entries ORDER BY kind, CASE period WHEN 'week' THEN 0 ELSE 1 END, rank""",
            connection,
            dtype={"rank": "int64", "listens": "int64", "listens_per_day": "float64"},
        )
    windows = frame[GROUP + ["start_utc", "end_utc"]].drop_duplicates()
    if windows.duplicated(GROUP).any():
        raise ValueError("Analysis expects one chart window per kind and period")
    csv_output = output / "analysis"
    figures = output / "figures"
    csv_output.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    frame["window_days"] = (
        pd.to_datetime(frame["end_utc"], utc=True, format="ISO8601")
        - pd.to_datetime(frame["start_utc"], utc=True, format="ISO8601")
    ).dt.total_seconds() / 86_400
    frame["chart_share"] = frame["listens"] / frame.groupby(GROUP)["listens"].transform("sum")

    charts = _window_stats(frame, csv_output)
    ranks, comparisons = _rank_pivot(frame, csv_output)
    weekly_recordings = frame["kind"].eq("recording") & frame["period"].eq("week")
    median = frame.loc[weekly_recordings, "listens_per_day"].median()
    filtered = frame.loc[weekly_recordings & frame["rank"].le(20) & frame["listens_per_day"].ge(median)]
    filtered.to_csv(csv_output / "weekly_recording_filter.csv", index=False)

    _leader_figure(frame, "artist", figures / "artists.png")
    _leader_figure(frame, "recording", figures / "recordings.png")
    _comparison_figure(frame, ranks, figures / "cross_window.png")
    return {
        "rows": len(frame), "charts": charts, "comparisons": comparisons,
        "filtered_weekly_recordings": len(filtered),
        "weekly_recording_filter_median_listens_per_day": float(median) if weekly_recordings.any() else None,
        "figure_captions": _captions(charts, comparisons),
    }
