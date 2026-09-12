# Errors

Command failures and integration errors.

---

## [ERR-20260910-002] uv-cache-permission

**Logged**: 2026-09-10
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The default uv cache directory was not writable by the sandbox.

### Error
`Failed to initialize cache ... 拒绝访问。`

### Context
- `uv run` initially targeted the user cache under `C:\Users\User\AppData\Local\uv\cache`.
- Setting `UV_CACHE_DIR` to a writable project-local directory resolved the issue.

### Metadata
- Reproducible: yes
- Related Files: fetch_papers.py

### Resolution
- **Resolved**: 2026-09-10
- **Notes**: Verification commands now use `.uv-cache` under the project root.

---

## [ERR-20260910-001] python-executable

**Logged**: 2026-09-10
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
The `python` launcher is present via WindowsApps but cannot start in this environment.

### Error
`程序“python.exe”无法运行: 系统无法访问此文件。`

### Context
- Attempted `python -m py_compile fetch_papers.py` and an inline parser smoke test.
- `Get-Command` resolves `python.exe` to `C:\Users\User\AppData\Local\Microsoft\WindowsApps\python.exe`.

### Suggested Fix
Install or expose a working Python interpreter before running automated verification.

### Metadata
- Reproducible: unknown
- Related Files: fetch_papers.py

---
