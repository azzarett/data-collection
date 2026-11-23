"""Rebuild the English PDF from the submitted snapshot and its run evidence."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results"
HERE = ROOT / "report"
INK = "#202832"
ACCENT = "#253F59"
LIGHT = "#F0F3F6"
WIDTH = A4[0] - 38 * mm - 12


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def style(name, font, size, leading, color=INK, after=6, alignment=TA_LEFT):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading,
                          textColor=colors.HexColor(color), spaceAfter=after, alignment=alignment)


STYLES = {
    "university": style("University", "Times-Bold", 18, 24, alignment=TA_CENTER),
    "title": style("Title", "Times-Bold", 28, 33, alignment=TA_CENTER),
    "cover": style("Cover", "Times-Roman", 14, 20, alignment=TA_CENTER),
    "h": style("Heading", "Times-Bold", 20, 24, after=12),
    "sub": style("Subhead", "Times-Bold", 14, 17, ACCENT, 4),
    "body": style("Body", "Times-Roman", 11.5, 15, after=8),
    "caption": style("Caption", "Helvetica", 9, 12.4, "#405B62", 10),
    "code": style("Code", "Courier", 8.4, 12, after=8),
}


def p(value, key="body"):
    return Paragraph(value, STYLES[key])


def tab(rows, widths):
    cells = []
    for n, row in enumerate(rows):
        cell_style = style("Cell", "Helvetica-Bold" if not n else "Helvetica", 9.2, 12,
                           "#FFFFFF" if not n else INK, 0)
        cells.append([Paragraph(escape(str(value)), cell_style) for value in row])
    table = Table(cells, colWidths=[WIDTH * x for x in widths], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ACCENT)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(LIGHT), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def graph(path):
    chart = Image(str(path))
    chart.drawHeight = WIDTH * chart.imageHeight / chart.imageWidth
    chart.drawWidth = WIDTH
    return chart


def architecture():
    d = Drawing(WIDTH, 118)
    w = (WIDTH - 40) / 3
    labels = [("API client", "Four JSON responses"), ("Producer", "One row per message"),
              ("Kafka broker", "Topic / partition 0"), ("EDA", "Tables and figures"),
              ("SQLite", "Transactional load"), ("Consumer + Pandera", "Decode, validate, clean")]
    for i, (title, desc) in enumerate(labels):
        x, y = (i % 3) * (w + 20), 68 if i < 3 else 6
        d.add(Rect(x, y, w, 43, fillColor=colors.HexColor(LIGHT), strokeColor=colors.HexColor("#BFCAD4")))
        d.add(String(x + 9, y + 25, title, fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor(ACCENT)))
        d.add(String(x + 9, y + 10, desc, fontName="Helvetica", fontSize=9, fillColor=colors.HexColor(INK)))
    for i in range(2):
        left = w + i * (w + 20)
        for y, direction in [(89, 1), (27, -1)]:
            start, end = (left + 2, left + 17) if direction == 1 else (left + 18, left + 3)
            d.add(Line(start, y, end, y, strokeColor=colors.HexColor(ACCENT)))
            d.add(Polygon([end,y,end-4*direction,y+2,end-4*direction,y-2], fillColor=colors.HexColor(ACCENT),strokeColor=None))
    x = WIDTH - w / 2
    d.add(Line(x, 68, x, 51, strokeColor=colors.HexColor(ACCENT)))
    d.add(Polygon([x,50,x-3,55,x+3,55], fillColor=colors.HexColor(ACCENT), strokeColor=None))
    return d


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(INK))
    canvas.setFont("Times-Roman", 10)
    canvas.drawCentredString(A4[0] / 2, 13 * mm, str(doc.page))
    canvas.restoreState()


def build():
    ev = read(RUN / "verification.json")
    receipt = read(RUN / "receipt.json")
    snapshot = read(ROOT / "data/snapshot.json")
    demo = read(RUN / "invalid_examples.json")
    counts, cleaning, eda = ev["counts"], ev["cleaning"], ev["analysis"]
    charts, captions = eda["charts"], eda["figure_captions"]
    wk, mo = charts["artist_week"], charts["artist_month"]
    first, second = ev["database"]["loads"]
    figures = RUN / "figures"
    story = []
    add = story.extend
    page = PageBreak
    heading = lambda s: p(s, "h")
    sub = lambda s: p(s, "sub")
    cap = lambda s: p(s, "caption")
    code = lambda s: Preformatted(s, STYLES["code"])
    add([Spacer(1, 11 * mm),
         p("Kazakh-British Technical University", "university"),
         Spacer(1, 39 * mm),
         p("Project Report", "cover"),
         p("Music Listening Trends", "title"),
         p("Analysis of Popular Artists and Songs on ListenBrainz", "cover"),
         Spacer(1, 12 * mm),
         p("Data Collection &amp; Preparation", "cover"),
         Spacer(1, 32 * mm),
         p("<i>Authors</i>", "cover"),
         p("Temirkhan Adilet<br/>Bertayev Azat", "cover"),
         page(), heading("1. Introduction"),
         p("ListenBrainz ranks artists and recordings by the number of listens submitted by its users. "
           "This study compares the leaders, the share of listens held by the highest-ranked entries, "
           "and the ranks of artists and recordings that appear in both the weekly and monthly charts."),
         p(f"The first-ranked {escape(wk['leader']['name'])} entry accounted for {wk['leader']['chart_share']:.1%} "
           f"of listens among the weekly top 100 and {mo['leader']['chart_share']:.1%} among the monthly top 100. "
           "The analysis uses within-chart shares and daily averages to account for differences in window length. "
           "The pipeline verifies message delivery and tests whether a second database load preserves every stored value."),
         Spacer(1, 5)])

    # Report the actual bounds from each API response.
    rows = [["Chart","UTC start","UTC end","Positions","Chart listens"]]
    for label, ch in charts.items():
        rows.append([label.replace("_"," / "), ch["start_utc"][:10], ch["end_utc"][:10],ch["rows"],f'{ch["total_listens"]:,}'])
    add([heading("2. Data source and collection"),
         p("Each observation represents one position in a sitewide artist or recording chart for a specified period. The collector retrieves these charts through the public JSON API."),
         sub("Four public GET requests"),
         code("https://api.listenbrainz.org/1/stats/sitewide/artists\nhttps://api.listenbrainz.org/1/stats/sitewide/recordings\nrange=week or month     count=100     offset=0"),
         p("The archive (data/snapshot.json) preserves each response, URL, request parameters and retrieval time. Each payload contains the ordered chart, count, range, offset, time bounds and last update. Array order determines the one-based rank."),
         cap(f"Snapshot fetched on {snapshot['pages'][0]['retrieved_utc'][:10]} UTC. Table 1 shows the API windows. The right boundary is used as the endpoint for calculating elapsed days."),
         tab(rows,[.23,.18,.18,.15,.26]),Spacer(1,8),
         sub("Fields and sample observations"),
         p("Rank and listen count are numeric. Artist, title and MusicBrainz ID describe each entry. Unix timestamps delimit the window. The archive retains release and cover-art metadata where available."),
         tab([["Weekly position","Artist","Title","Listens"],
              ["Artist #1",wk["leader"]["name"],"N/A",f'{wk["leader"]["listens"]:,}'],
              ["Recording #1",snapshot["pages"][2]["response"]["payload"]["recordings"][0]["artist_name"],
               snapshot["pages"][2]["response"]["payload"]["recordings"][0]["track_name"],f'{charts["recording_week"]["leader"]["listens"]:,}']], [.30,.23,.25,.22]),
         Spacer(1,6),p("Requests have timeouts and retry transient errors. Incomplete charts halt collection. The archive preserves the dataset when the public rankings change.")])

    add([page(),heading("3. Pipeline architecture"),architecture(),
         cap("Figure 1. Data flow from the ListenBrainz API to the analytical outputs. The consumer reads only the offsets acknowledged for this batch. Quarantined rows are written to a separate JSON file."),
         p("The collector flattens the four source arrays. The producer sends those rows to the broker. The consumer decodes them and the runner compares their ordered content with the original input. Validated rows reach pandas, NumPy and SQLite. Analysis opens the verified database in read-only mode."),
         sub("4. Apache Kafka implementation"),
         p("Compose runs apache/kafka:4.0.2 as a single KRaft broker/controller, exposed on localhost port 9092. The topic uses one partition and replication factor one. This configuration preserves message order within the batch. A broker outage interrupts processing until the broker is available again."),
         code('json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8")\nconsumer.assign([assigned])\nconsumer.seek(assigned, offsets[0])\nrecord = json.loads(message.value)'),
         cap("Selected lines from src/producer.py and src/consumer.py. Each message also carries its run ID and zero-based input index as headers."),
         p("The producer enables idempotence and waits for broker acknowledgements with acks=all. The receipt lists each acknowledged offset. The consumer verifies the run header and index at each expected offset and stops after the acknowledged count. A timeout, wrong header or skipped expected offset ends the run with an error."),
         tab([["Topic / partition","Acknowledged offsets","Sent / received"],
              [f'{receipt["topic"]} / {receipt["partition"]}',f'{receipt["offsets"][0]} through {receipt["offsets"][-1]}',f'{receipt["count"]} / {counts["consumed"]}']], [.41,.31,.28]),
         Spacer(1,9),cap(f"Table 2. Actual broker receipt. Run ID {receipt['run_id']}. Replays assign a new run ID and offsets.")])

    add([page(),heading("5. Pandera validation"),
         p("Validation operates on the decoded JSON values before type coercion. Lazy checks retain the input row index for every failing rule. Rows passing all checks proceed to cleaning. Rejected rows retain their payload, index and reasons in quarantine.json."),
         tab([["Fields","Acceptance rule"],
              ["kind / period","artist or recording; week or month."],
              ["rank / listens","Rank is an integer from 1 to 100. Listens is a positive integer that fits SQLite. Booleans and strings fail."],
              ["artist_name / track_name","Artist name has non-whitespace text. Recordings require a title. Artist chart rows have a null title."],
              ["mbid","An optional identifier must have UUID syntax when supplied."],
              ["from_ts / to_ts","Bounded integer seconds, with the end strictly after the start."]], [.29,.71]),
         Spacer(1,9),p(f"All {counts['valid']} archive rows passed. The weekly leader in Section 2 illustrates a valid record. Four isolated copies of a valid row exercise the rejection path."),
         tab([["Deliberate defect","Observed rule failure"]] +
             [[case["case"],", ".join(case["errors"])] for case in demo], [.40,.60]),
         Spacer(1,9),sub("6. Cleaning and transformation"),
         p(f"The {cleaning['missing_before']['track_name']} absent track titles belong to artist charts. The {cleaning['name_fallback_rows']} entries without an MBID use a normalized artist/title key. Other required fields were present. Unicode NFC, whitespace normalization and trimming changed {cleaning['normalized_text_cells']} text cells. Exact clean-row comparisons removed {cleaning['duplicates_removed']} duplicates."),
         p("Rank and listens become int64. UTC seconds become ISO timestamps. NumPy divides listens by elapsed days so the two window lengths are comparable. Conflicting data at the same chart position stops the load. Sections 7 and 8 show how the key, filter, grouped statistics and rank pivot use these transformations.")])

    add([page(),heading("7. SQLite storage"),
         p("charts.db contains one table, chart_entries. Its 11 fields retain the chart coordinates, display names, optional MBID, comparison key, total listens and daily rate. TEXT fields store ISO UTC times. INTEGER stores ranks and counts. REAL stores the derived daily rate."),
         code("PRIMARY KEY (kind, period, start_utc, end_utc, rank)"),
         p("Two positions may legitimately refer to the same recording. The primary key identifies a position, while entity_key links observations of the same artist or recording. CHECK constraints enforce the categories, positive values and title rules."),
         p("The loader binds parameters inside a transaction. ON CONFLICT on the primary key skips an existing position. It then hashes every ordered database field and compares it to the clean input before commit. A different value at an existing key causes rollback."),
         graph(HERE / "sql-check.png"),
         cap("Figure 2. Browser capture of sqlite3 output from sql/verify.sql on the submitted database. Positions span 1 through 100 in each chart. Distinct recording identities can be fewer than positions. The final checks count repeated positions and verify SQLite integrity.")])

    add([page(),heading("8. Exploratory data analysis"),
         p("Each comparison uses one chart and period at a time. Artist and recording totals measure different groupings of listening activity. Adding them would count some listening twice."),
         graph(figures / "artists.png"), cap("Figure 3. " + escape(captions["artists.png"]) + " BTS also appears at a lower rank without an MBID in both charts. The percentages refer to the first-ranked entry."),
         graph(figures / "recordings.png"),cap("Figure 4. " + escape(captions["recordings.png"])),
         p("Each bar retains the source rank. Repeated titles can reflect distinct source entries. Daily averages divide each chart count by its full observed window and do not describe a particular day's activity.")])

    summary_rows = [["Chart","Distinct artist names","Distinct entities","Median listens","Top 10 share"]]
    for k,c in charts.items():
        summary_rows.append([k.replace("_"," / "),c["distinct_artist_names"],c["distinct_entities"],
                             f'{c["median_listens"]:,.1f}',f'{c["top_10_share"]:.1%}'])
    add([page(),heading("Rank overlap and concentration"),
         graph(figures / "cross_window.png"),cap("Figure 5. " + escape(captions["cross_window.png"])),
         sub("Grouped and categorical results"),tab(summary_rows,[.23,.20,.18,.22,.17]),
         Spacer(1,7),cap("Table 3. Medians describe ranked entries. Entity counts use the MBID or the normalized-name fallback. The top-ten share divides the first ten positions' listens by the sum for all retained positions in that same chart."),
         p("The pivot uses kind and entity_key as its index, period as columns and minimum rank as the aggregation. A blank cell means the entity fell outside the captured list or could not be matched. The diagonal in Figure 5 marks the same rank in both windows."),
         p(f"The median absolute movement among shared entities was {eda['comparisons']['artist']['median_absolute_rank_change']:.0f} places for artists and {eda['comparisons']['recording']['median_absolute_rank_change']:.0f} for recordings. Recordings showed more rank movement between these windows."),
         p(f"A combined filter selected {eda['filtered_weekly_recordings']} weekly recording positions ranked 1-20 with a daily rate at or above the weekly recording median of {eda['weekly_recording_filter_median_listens_per_day']:,.1f}. The weekly artist positions had a mean of 20,424.1 listens and a median of 11,166. A small number of leaders pull the mean upward. The analysis CSVs also report quartiles and dispersion.")])

    add([page(),heading("9. Pipeline testing and verification"),
         tab([["Stage","Rows","Check"],
              ["API / producer",str(counts["collected"]),"Four complete responses; every send acknowledged."],
              ["Consumer",str(counts["consumed"]),"All acknowledged offsets read. Ordered JSON digest equals input."],
              ["Pandera",f'{counts["valid"]} / {counts["invalid"]}',"Valid / invalid production rows; deliberate examples excluded."],
              ["Clean / store",f'{counts["cleaned"]} / {counts["stored"]}',"Clean and stored rows agree on all fields."],
              ["Second load",str(second["inserted"]),"Additional rows inserted. Count and content digest preserved."],
              ["EDA",str(eda["rows"]),"Analysis opened the verified SQLite database."]], [.23,.15,.62]),
         Spacer(1,12),p(f"Table 4. The first load inserted {first['inserted']} rows. Both database reads produced the same SHA-256 over the ordered row values."),
         code(first["sha256"]),
         p("Tests exercise the four-chart minimum, incomplete archives, isolated invalid examples, mixed JSON types, normalization and deduplication, repeated entities at different positions, conflicting positions and transactional rollback. Terminal commands and expected values are recorded in the README."),
         sub("10. Conclusions"),
         p(f"{escape(wk['leader']['name'])} leads both artist charts. The weekly top ten recording positions account for {charts['recording_week']['top_10_share']:.1%} of retained listens. The October top ten account for {charts['recording_month']['top_10_share']:.1%}. Listening within the captured weekly chart was more concentrated."),
         p("The main technical challenge was defining a duplicate. Repeated MusicBrainz IDs across ranks are present in the API itself. Retaining source positions preserves the chart, while taking each identity's best rank enables meaningful cross-window matching."),
         p("The API summarizes the ListenBrainz community. The top-100 cutoff excludes the long tail, and repeated listens do not reveal the number of distinct listeners. Name-based matching can merge namesakes or miss spelling variants. Two windows of unequal length support a comparison of observed ranks and average daily counts. Inferring a long-term trend or its cause would require more windows and listener-level evidence.")])

    sources = [("ListenBrainz","Statistics API","https://listenbrainz.readthedocs.io/en/latest/users/api/statistics.html"),
               ("Apache Kafka","Running Kafka with Docker","https://kafka.apache.org/40/getting-started/docker/"),
               ("Pandera","Lazy validation and failure cases","https://pandera.readthedocs.io/en/stable/lazy_validation.html"),
               ("pandas","Pivot tables and aggregation","https://pandas.pydata.org/docs/reference/api/pandas.pivot_table.html"),
               ("NumPy","Element-wise division","https://numpy.org/doc/stable/reference/generated/numpy.divide.html"),
               ("SQLite","UPSERT and conflict handling","https://www.sqlite.org/lang_upsert.html"),
               ("Matplotlib","Horizontal bar charts","https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.barh.html")]
    add([page(),heading("11. Individual contributions"),
         p("Table 5 presents each author’s assigned responsibilities for the implementation review and oral defense."),
         tab([["Author","Assigned responsibilities"],
              ["Temirkhan Adilet","Source selection and HTTP collection, raw snapshot and ranking semantics, Kafka broker and topic, producer and consumer, message verification and transport troubleshooting."],
              ["Bertayev Azat","Pandera schema and negative tests, pandas and NumPy transformations, SQLite design and idempotence, statistical analysis, charts and interpretation."]], [.32,.68]),
         Spacer(1,14),p("Both authors share responsibility for reproducing the end-to-end run, reviewing the documentation and verifying the reported results."),
         sub("12. References"),
         *[p(f'<b>{name}</b> &nbsp; <link href="{url}" color="{ACCENT}"><u>{title}</u></link>') for name,title,url in sources],
         Spacer(1,10),sub("Reproduction materials"),
         p("The repository contains the original API responses, source modules, broker configuration, dependency pins, validation tests, SQL, figures and machine-readable run evidence. The README gives the execution order and verification commands. docs/data_dictionary.md defines the fields and docs/defense.md gives the live demonstration sequence.")])
    doc = SimpleDocTemplate(str(HERE / "project_report.pdf"), pagesize=A4, leftMargin=19*mm,
                            rightMargin=19*mm, topMargin=22*mm, bottomMargin=22*mm,
                            title="Music Listening Trends | ListenBrainz", author="Temirkhan Adilet and Bertayev Azat")
    doc.build(story, onLaterPages=footer)


if __name__ == "__main__":
    build()
