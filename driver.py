from __future__ import annotations

import uvicorn
from backend.core.memory import boot_restore_state


def main() -> None:
    boot_restore_state()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8010, reload=False)


if __name__ == "__main__":
    main()