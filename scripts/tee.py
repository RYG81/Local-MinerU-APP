# Tiny cross-platform tee: stdin -> console + logfile.
# Reads RAW CHUNKS (not lines) so tqdm progress bars (\r updates
# without newline) appear live in the console instead of making the
# window look frozen while the engine is busy.
import sys

logfile = sys.argv[1]
stdin = sys.stdin.buffer
stdout = sys.stdout.buffer
with open(logfile, "ab") as f:
    while True:
        chunk = stdin.read(1)
        if not chunk:
            break
        # read whatever else is immediately available for efficiency
        try:
            import os
            extra = stdin.read1(65536) if hasattr(stdin, "read1") else b""
            chunk += extra
        except Exception:
            pass
        try:
            stdout.write(chunk)
            stdout.flush()
        except Exception:
            pass
        # keep the logfile readable: convert bare \r updates to newlines
        f.write(chunk.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
        f.flush()
