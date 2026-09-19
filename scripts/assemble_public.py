import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
PUBLIC = os.path.join(ROOT, "public")


def main() -> int:
    if not os.path.isfile(os.path.join(DIST, "index.html")):
        print(f"ERROR: '{os.path.join(DIST, 'index.html')}' not found. Run `npm run build` first.", file=sys.stderr)
        return 1
    if os.path.isdir(PUBLIC):
        shutil.rmtree(PUBLIC)
    shutil.copytree(DIST, PUBLIC)
    print(f"Assembled public/ from dist/ ({len(os.listdir(PUBLIC))} top-level entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())