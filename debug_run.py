import sys
from pathlib import Path

# Fix sys.path if needed
sys.path.append(str(Path(__file__).parent))

import queue
from app.core.pipeline import PipelineRunner

q = queue.Queue()
print("Starting PipelineRunner in debug mode...")
runner = PipelineRunner("input", "", False, q)

# Run synchronously
runner._execute_pipeline()

# Drain the queue to see logs
while not q.empty():
    msg = q.get()
    print(f"[{msg.get('type')}] {msg.get('message')}")
    if msg.get("type") == "error":
        print(f"!!! ERROR: {msg.get('message')}")
