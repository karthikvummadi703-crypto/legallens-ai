from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

_ONE_YEAR = 60 * 60 * 24 * 365


class ImmutableStaticFiles(StaticFiles):
    """StaticFiles for content-hashed build assets.

    Vite fingerprints every file under ``/assets`` with a content hash, so a
    year-long immutable cache is safe and saves one round-trip on every
    browser visit.
    """

    def file_response(self, full_path, stat_result, scope, status_code=200):
        return FileResponse(
            full_path,
            status_code=status_code,
            stat_result=stat_result,
            headers={"Cache-Control": f"public, max-age={_ONE_YEAR}, immutable"},
        )
