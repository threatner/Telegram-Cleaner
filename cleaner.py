"""Legacy entry point. Prefer `python -m tgcleaner` or installing the package
and running `tgcleaner`. This wrapper exists so older instructions still work.
"""
from tgcleaner.cli import run

if __name__ == "__main__":
    run()
