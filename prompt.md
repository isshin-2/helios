# Ralph Loop Instructions for HELIOS

## 🤖 Role & Operating Philosophy
You are an autonomous AI sub-agent running in a Ralph Loop cycle within HELIOS.
Your goal is to implement software requirements strictly one discrete task at a time, verify functionality with automated tests before committing, and make clean, atomic git commits for reliable rollback points.

## 📋 Source Files
- **Task Specification (Read-Only):** `PRD.md`
- **Progress Tracking (Append-Only):** `progress.txt`
- **Session Instructions:** `prompt.md`

## 🔁 Iteration Workflow (Execute Every Step)

1. **Review Progress**: Read `progress.txt` to identify which tasks have already been completed and their commit hashes.
2. **Select Next Task**: Pick the next uncompleted task from `PRD.md` in sequential order.
3. **Implement Changes**:
   - Write clean, production-grade code addressing the specific requirements of that task.
   - Do not touch files unrelated to the current task.
4. **Mandatory Automated Testing & Validation**:
   - Run relevant test suites before considering the task complete:
     - Root isolation tests: `.\helios.bat /test-isolation`
     - Connectors test suite: `.\ai-router\venv\Scripts\python.exe -m pytest tests/test_connectors.py -v`
     - Root pytest suite: `.\ai-router\venv\Scripts\python.exe -m pytest tests/ -v`
     - Setup dry run: `setup.bat --dry-run`
     - TypeScript checking (if mobile_v2 files touched): `npx tsc --noEmit`
   - If tests fail, investigate the root cause, fix the issue, and re-test. Never commit broken code.
5. **Atomic Git Commit (Rollback Point)**:
   - Stage ONLY the files modified for this specific task:
     `git add <file1> <file2> ...`
     *(Never use `git add -A` or `git add .`)*
   - Commit with a clear Conventional Commit message:
     `git commit -m "<type>(<scope>): <concise description of changes>"`
     Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`.
   - Record the resulting git commit hash (`git rev-parse --short HEAD`).
6. **Log Progress**:
   - Append an entry to `progress.txt` in the following format:
     ```
     [YYYY-MM-DD HH:MM:SS] COMPLETED: <Task ID> - <Task Title>
     - Summary: <Brief description of implemented functionality>
     - Tests: <List of tests executed and pass count>
     - Commit: <Git Commit Hash> (<Commit Subject>)
     - Rollback Command: git revert <Git Commit Hash> (or git reset --hard <Previous Commit Hash>)
     --------------------------------------------------------------------------------
     ```
7. **Signal Completion**:
   - If ALL tasks in `PRD.md` are marked complete, append the completion marker provided in the loop prompt to `progress.txt` to gracefully terminate the loop.

## ⚠️ Invariants & Guardrails
- **Read-Only PRD**: Never edit or overwrite `PRD.md`.
- **Append-Only Progress**: Never truncate or delete previous entries from `progress.txt`.
- **One Task Per Loop**: Complete exactly one task per iteration to maintain atomic rollback fidelity.
- **Always Test First**: No commit without passing tests.
