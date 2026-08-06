#!/usr/bin/env python3
"""Локальный сервер с поддержкой Range — иначе видео не перематывается.

    cd web && python3 serve.py        # → http://localhost:8749/

Штатный `python3 -m http.server` отдаёт файл только целиком: браузер не может
запросить кусок с середины, поэтому полоса прокрутки у <video> не работает.
"""
import http.server, os, re, socketserver, sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8749


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(f.fileno()).st_size
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            f.close()
            self.send_error(400, "Bad Range")
            return None

        first, last = m.group(1), m.group(2)
        if first:
            start = int(first)
            end = int(last) if last else size - 1
        else:  # суффиксная форма: bytes=-500
            start = max(0, size - int(last))
            end = size - 1
        end = min(end, size - 1)

        if start > end or start >= size:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % size)
            self.end_headers()
            return None

        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        f.seek(start)
        self.range_remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "range_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        self.range_remaining = None
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def end_headers(self):
        if self.command == "GET" and not self.headers.get("Range"):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "favicon" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with Server(("", PORT), RangeHandler) as httpd:
        print("КП открыт: http://localhost:%d/  (Ctrl+C — остановить)" % PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nостановлен")
