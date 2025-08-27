# Documentation preview quickstart

Run the local MyST preview for this folder.

- Using the VS Code task (recommended):

  - Terminal > Run Task… > "Preview documentation"
  - It runs: `cd documentation && myst start`

- Using CLI (no global install needed):

  - macOS with Homebrew Node 20:
    ```bash
    export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
    cd documentation
    uvx --from mystmd myst start
    ```
  - Then open: http://localhost:3000
  - Stop with Ctrl+C

- Alternative with npx (if you prefer npm):
  ```bash
  cd documentation
  npx mystmd myst start
  ```

Notes

- Requires Node.js 20 or newer in your PATH.
- Run the command from the `documentation/` directory (don’t pass extra flags like `--config` or `--serve`).
