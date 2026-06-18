"""Simple web server for EML-SemZip.

Provides a web UI for uploading, compressing, and decompressing
EML hypergraphs via browser.
"""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add project root to sys.path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ..pipeline import Compressor, Decompressor
from ..models.hypergraph import EMLHypergraph
from ..io.report import CompressionReport
from ..kb.builtin_kb import create_builtin_kb


class EMLSemZipHandler(BaseHTTPRequestHandler):
    """HTTP request handler for EML-SemZip web UI."""

    def log_message(self, format: str, *args) -> None:
        """Print log messages to stderr."""
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_json(self, data: dict, status: int = 200) -> None:
        """Send JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content: str, status: int = 200) -> None:
        """Send HTML response."""
        body = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        """Read request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return b""
        return self.rfile.read(content_length)

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            template_path = Path(__file__).parent / "templates" / "index.html"
            if template_path.exists():
                with open(template_path, "r", encoding="utf-8") as f:
                    self._send_html(f.read())
            else:
                self._send_html("<h1>index.html not found</h1>", 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/api/compress":
            self._handle_compress()
        elif self.path == "/api/decompress":
            self._handle_decompress()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_compress(self) -> None:
        """Handle /api/compress request."""
        try:
            body = self._read_body()
            request = json.loads(body.decode("utf-8"))

            # Parse graph data
            graph_data = request.get("graph", {})
            theta_dead = request.get("theta_dead", 0.45)
            keep_ratio = request.get("keep_ratio", 0.15)
            use_builtin_kb = request.get("use_builtin_kb", False)

            # Reconstruct hypergraph
            from ..models.hyperedge import HyperEdge
            from ..models.node import Node

            graph = EMLHypergraph()
            for node_id, node_attrs in graph_data.get("nodes", {}).items():
                graph.add_node(Node(node_id, node_attrs))

            for edge_dict in graph_data.get("edges", []):
                edge = HyperEdge.from_dict(edge_dict)
                graph.add_edge(edge)

            # Compress
            kb = create_builtin_kb() if use_builtin_kb else None
            start_time = time.time()
            compressor = Compressor(kb=kb, theta_dead=theta_dead, keep_ratio=keep_ratio)
            compressed = compressor.compress(graph)
            elapsed_ms = (time.time() - start_time) * 1000

            # Count compressed edges
            compressed_edges = 0
            for stats in compressor.stats:
                if stats.stage_name == "stage4_ksnap_selection":
                    compressed_edges = stats.output_count

            # Report
            report = CompressionReport(
                original_nodes=graph.node_count(),
                original_edges=graph.edge_count(),
                compressed_bytes=len(compressed),
                original_bytes=len(json.dumps(graph_data).encode("utf-8")),
                theta_dead=theta_dead,
                keep_ratio=keep_ratio,
                compressed_edges=compressed_edges,
                stage_stats=[s.__dict__ for s in compressor.stats],
                elapsed_total_ms=elapsed_ms,
                timestamp=__import__("datetime").datetime.now().isoformat(),
            )

            self._send_json({
                "status": "ok",
                "compressed_bytes": len(compressed),
                "compressed_b64": base64.b64encode(compressed).decode("ascii"),
                "report": json.loads(report.to_json()),
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, 500)

    def _handle_decompress(self) -> None:
        """Handle /api/decompress request."""
        try:
            body = self._read_body()
            request = json.loads(body.decode("utf-8"))
            compressed_b64 = request.get("compressed_b64", "")
            use_builtin_kb = request.get("use_builtin_kb", False)

            compressed = base64.b64decode(compressed_b64)
            kb = create_builtin_kb() if use_builtin_kb else None

            decompressor = Decompressor(kb=kb)
            graph = decompressor.decompress(compressed)

            self._send_json({
                "status": "ok",
                "graph": graph.to_dict(),
                "nodes": graph.node_count(),
                "edges": graph.edge_count(),
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, 500)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start the EML-SemZip web server."""
    server = HTTPServer((host, port), EMLSemZipHandler)
    print(f"EML-SemZip Web UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    run_server()
