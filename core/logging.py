"""
Custom logging handlers for Windows compatibility.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that closes its stream before renaming on Windows.

    Always opens the log file as UTF-8. Without this the file inherits the
    console codepage (cp1252 on Windows) and any non-ASCII character — an
    emoji in an email subject, an accented name — raises
    ``UnicodeEncodeError`` *inside the logger*, which turns a harmless log
    line into a noisy "--- Logging error ---" traceback.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('encoding', 'utf-8')
        kwargs.setdefault('errors', 'replace')
        super().__init__(*args, **kwargs)

    def rotate(self, source, dest):
        if self.stream:
            self.stream.close()
            self.stream = None
        try:
            if os.path.exists(dest):
                os.remove(dest)
            os.rename(source, dest)
        except PermissionError:
            # File still held by another process — skip this rotation cycle
            pass
        if not self.delay:
            self.stream = self._open()


class UTF8StreamHandler(logging.StreamHandler):
    """
    StreamHandler that always writes UTF-8 to stdout on Windows.

    Uses sys.stdout lazily on every emit() so the handler survives Daphne's
    autoreloader replacing/closing the original stdout stream.  Swallows
    ValueError/OSError so a closed-stream during reload never crashes the
    server process.
    """

    def emit(self, record):
        try:
            msg = self.format(record) + self.terminator
            out = sys.stdout
            # Write raw UTF-8 bytes directly when a binary buffer is available.
            # This bypasses the stream's codec (cp1252 on Windows) entirely.
            buf = getattr(out, 'buffer', None)
            if buf is not None and not getattr(buf, 'closed', False):
                buf.write(msg.encode('utf-8', errors='replace'))
                buf.flush()
            else:
                # Fallback: plain text write (may fail for non-ASCII on cp1252)
                out.write(msg)
                out.flush()
        except (ValueError, OSError):
            # Stream closed during Daphne reload — drop the record silently.
            pass
