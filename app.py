from __future__ import annotations

import json
import traceback
from typing import Generator

from flask import Flask, Response, jsonify, request, stream_with_context

from core.utils.logger import Logger, Verbosity
from core.ingestors.MainIngestor import MainIngestor
from core.chains.report_generation import get_prethinking, get_report
from core.chains.llm import GeminiLLM, SuperGemini

import os
LOCAL = os.getenv("DOCKER", "false").lower() == "false"
from dotenv import load_dotenv
load_dotenv()
PORT = int(os.getenv("PORT", 8080))
app = Flask(__name__)
if LOCAL:
    #if this isnt importing make sure u hv pip installed dev_requirements.txt
    from flask_cors import CORS
    CORS(app)
log = Logger(name=__name__, verbosity=Verbosity.DEBUG)
log.debug(f"Environment: LOCAL={LOCAL}, PORT={PORT}")

llm = SuperGemini(init_health_check=False)
mig = MainIngestor(parallel=False)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict | list) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _sse_response(generator) -> Response:
    return Response(
        stream_with_context(generator),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


def _parse_body() -> tuple[str, int]:
    body    = request.get_json(silent=True) or {}
    product = body.get("product", "").strip()
    limit   = int(body.get("limit", 25))
    return product, limit


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "nanbread-api"}), 200


# ---------------------------------------------------------------------------
# POST /report  (blocking — wired up same as stream but no SSE)
# ---------------------------------------------------------------------------

@app.post("/report")
def report():
    product, limit = _parse_body()
    if not product:
        return jsonify({"error": "Missing required field: product"}), 400

    log.info(f"POST /report — product=[cyan]{product}[/cyan]")

    try:
        prethinking_result = get_prethinking(llm, product)
        queries = prethinking_result.get("queries", [])

        origins, url_map = mig.get_origins(queries, caps={"reddit": 3, "youtube": 3, "twitter": 3})
        comments = mig.get_comments(origins)
        report_data = get_report(llm, product, comments)

        return jsonify({"report": report_data, "url_map": url_map}), 200

    except Exception as exc:
        log.error(f"POST /report failed: {exc}")
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /report/stream  (SSE)
# ---------------------------------------------------------------------------

@app.post("/report/stream")
def report_stream():
    product, limit = _parse_body()
    if not product:
        return jsonify({"error": "Missing required field: product"}), 400

    log.info(f"POST /report/stream — product=[cyan]{product}[/cyan]")

    def event_generator() -> Generator[str, None, None]:
        try:
            # ----------------------------------------------------------------
            # Stage 1 — prethinking
            # LLM decides what queries to search for
            # ----------------------------------------------------------------
            log.info("[bold]Stage 1[/bold] — prethinking")
            prethinking_result = get_prethinking(llm, product)
            thinking_text = prethinking_result.get("thinking", "")
            queries       = prethinking_result.get("queries", [])
            log.debug(f"Prethinking: [blue]{thinking_text}[/]")
            log.debug(f"Got [cyan]{len(queries)}[/cyan] queries: {queries}")

            # matches dummy: {"queries": [...], "thinking": "..."}
            yield _sse("prethinking", {
                "thinking": thinking_text,
                "queries":  queries,
            })

            # ----------------------------------------------------------------
            # Stage 2 — origins / urls
            # Run all ingestors to get thread/video/tweet URLs
            # ----------------------------------------------------------------
            log.info("[bold]Stage 2[/bold] — fetching origins")
            origins, url_map = mig.get_origins(
                queries,
                caps={"reddit": 2, "youtube": 2, "twitter": 2},
            )
            log.debug(f"Got {len(origins)} origins")
            for o in origins:
                log.trace(f"  {o['idx']} [{o['source']}] {o['url']}")

            # matches dummy: {"urls": [{"source": "reddit", "url": "..."}, ...]}
            flat_urls_list = [{"source": o["source"], "url": o["url"]} for o in origins]
            yield _sse("urls", {
                "urls": flat_urls_list[:7]
            })

            # ----------------------------------------------------------------
            # Stage 3 — comments
            # Fetch actual comments from each origin
            # ----------------------------------------------------------------
            log.info("[bold]Stage 3[/bold] — fetching comments")
            comments = mig.get_comments(origins)
            total_comments = sum(len(c["comments"]) for c in comments)
            log.debug(f"Got [cyan]{total_comments}[/cyan] total comments across {len(origins)} origins")

            # matches dummy: {"comments": [{"comment": "...", "source": "reddit"}, ...]}
            # resolve source by looking up idx in origins
            idx_to_source = {o["idx"]: o["source"] for o in origins}
            flat_comments = [
                {"comment": comment, "source": idx_to_source.get(c["idx"], "unknown")}
                for c in comments
                for comment in c["comments"]
            ]
            yield _sse("comments", {"comments": flat_comments[:10]})

            # ----------------------------------------------------------------
            # Stage 4 — postthinking (hardcoded for now)
            # ----------------------------------------------------------------
            log.info("[bold]Stage 4[/bold] — postthinking")
            yield _sse("postthinking", {
                "thoughts": [
                    f"Reading through {total_comments} comments across {len(origins)} sources...",
                    f"Identifying key themes for {product}...",
                    "Analysing sentiment across platforms...",
                    "Cross-referencing recurring complaints and praise...",
                    "Structuring findings into report sections...",
                ]
            })

            # ----------------------------------------------------------------
            # Stage 5 — report
            # LLM generates structured report from comments
            # ----------------------------------------------------------------
            log.info("[bold]Stage 5[/bold] — generating report")
            report_data = get_report(llm, product, comments)
            log.debug(f"Sample report section: [blue]{report_data.get('sections', [{}])[0].get('content', '')[:200]}[/]")
            log.info("[bold green]Report generated successfully[/bold green]")

            # matches dummy: full report object + url_map for reference resolution
            yield _sse("report", {
                **report_data,
                "url_map": url_map,
            })

        except Exception as exc:
            log.error(f"Stream error: {exc}\n{traceback.format_exc()}")
            yield _sse("error", {"message": str(exc)})

    return _sse_response(event_generator())


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(f"Starting [bold]NanBread API[/bold] on [cyan]http://localhost:{PORT}[/cyan]")
    app.run(debug=True, port=PORT)