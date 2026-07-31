"""One module per analysis stage, plus the pipeline that sequences them.

Each stage module exposes a single `run(...)` function so that adding,
reordering or disabling a stage is a change in `pipeline.py` alone.
"""
