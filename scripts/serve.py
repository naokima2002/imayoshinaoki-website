#!/usr/bin/env python3
"""Simple dev server for imayoshinaoki-website"""
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3456

os.chdir(ROOT)
print(f"Serving {ROOT} at http://localhost:{PORT}")
HTTPServer(("", PORT), SimpleHTTPRequestHandler).serve_forever()
