# Errors

Command failures and integration errors.

---

## [ERR-20260912-001] git-refs-remotes-silently-lost

**Logged**: 2026-09-12
**Priority**: low (本地显示问题,不影响提交与推送)
**Status**: workaround
**Area**: tooling

### Summary
`git update-ref`(以及 `git fetch`)写入 `refs/remotes/**` 下的任何 ref 时,
**退出码 0 且报告成功,但目标 ref 并不存在**——实际发生的是该目录被删掉。

### Error
无报错。`git fetch origin` 打印 `* [new branch] main -> origin/main`、`exit=0`,
但紧接着 `git rev-parse refs/remotes/origin/main` 报
`unknown revision or path not in the working tree`,
且 `refs/remotes/origin/` 目录根本不存在。

### Context
- 环境:`git version 2.55.0.windows.3`(WorkBuddy 自带的 PortableGit),Windows。
- 复现步骤(最小):
  ```bash
  mkdir -p .git/refs/remotes/origin
  printf '<sha>\n' > .git/refs/remotes/origin/main   # 手写:成功,能读回
  git update-ref refs/remotes/origin/probe <sha>     # exit=0,但整个 origin/ 目录被删
  ```
- **影响范围经对照实验确认,只限于 `refs/remotes/**`**:
  `refs/heads/**`、`refs/tags/**`、`refs/custom/**` 全部正常创建。
- **不是 shell 沙箱造成的**:在 Bash 与 PowerShell 两个执行通道下行为完全一致。
- 仓库本身无异常:普通 `.git` 目录、无 reftable、无 `GIT_DIR` 重定向、
  `core.logallrefupdates=true`、无自定义 hook、`packed-refs` 不存在。
- 手写该文件后 `git branch -vv` 能正确显示 `[origin/main]`,
  说明 git 的**读取**路径正常,**写入**路径有问题。

### Suggested Fix
推送/拉取本身不受影响(用显式 refspec 即可,如 `git push origin main`)。
只需要远端跟踪 ref 时,手工补一个文件:
```bash
mkdir -p .git/refs/remotes/origin
printf '<sha>\n' > .git/refs/remotes/origin/main
```
注意:**此后任何一次 `git fetch` 都会再次把它删掉**,所以这是临时手段,
不是修复。彻底解决要么换 git 版本,要么接受本地不显示 ahead/behind。

### Metadata
- Reproducible: yes
- Related Files: .git/refs/remotes

### Resolution
- **Status**: workaround (未根治,环境/工具链缺陷)
- **Notes**: 已确认提交与推送正常(`be38563..07affbc main -> main`,
  远端 `git ls-remote origin refs/heads/main` 返回 `07affbc`),
  仅本地 tracking ref 受影响。

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
**Status**: resolved
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

### Resolution
- **Resolved**: 2026-09-12
- **Notes**: Use the managed interpreter instead of the WindowsApps stub:
  `C:\Users\User\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe`
  (Python 3.13.14). Verified with
  `"<managed python>" -m unittest discover -s tests` → 17 passed.
  Keep using `UV_CACHE_DIR=.uv-cache` for any `uv` invocation.

---
