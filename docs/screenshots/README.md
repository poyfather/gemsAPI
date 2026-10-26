# Screenshots

The pictures in the main README, and how to make them again. They are taken from a real Lapidary with a real model; nothing in them is mocked except the Windows PC behind the two console pictures.

| File | What it shows |
|---|---|
| `compare-answers.png` | The Compare page: version 1 and version 2 of `code_reviewer` answering one question side by side. Its answers are the side by side moment of the demo video in `../demo/`. |
| `compare-tests.png` | The same two versions through the four tests. In the run pictured, version 1 passed 1 of 4 and version 2 passed 3 of 4; the recorded runs on the prompt's page gave 2 of 4 and 4 of 4. A 4B model varies from run to run. |
| `prompt-page.png` | `code_reviewer`'s page: its tests with past scores against the baseline, and its history with the diff from version 1 to version 2. |
| `library.png` | The library of prompts and assistants. |
| `chat.png` | Chat with the improved `code_reviewer`. |
| `console-start.png`, `console-doctor.png` | Lapidary Console's first run and its Doctor. |

## How they were made

- **Model.** qwen3:4b on [Ollama](https://ollama.com) 0.40.11, the console's default local model, on an Apple M1 Max. With Lapidary's default model policy set to local, every answer, score and judgment came from that model. Answers vary from run to run; the scores in the pictures are the ones those runs gave.
- **Backend.** A fresh SQLite file, so the library is the shipped seed gems:
  ```sh
  GEMS_STORAGE=sqlite GEMS_SQLITE_PATH=/tmp/demo.db GEMS_MODEL_POLICY=local \
  LOCAL_OPENAI_BASE_URL=http://127.0.0.1:11434/v1 uvicorn app.main:app --port 8000
  ```
  Before seeding, set `code_reviewer`'s provider to `local` and its model to `qwen3:4b`, so its pages name the model that answers.
- **Demo data.** [`tools/seed_demo.py`](tools/seed_demo.py) adds the four tests to `code_reviewer`, runs them on version 1 and makes that the baseline, saves version 2 with one added paragraph, and runs the tests again.
- **The web UI.** It runs on port 3000 with the same `GEMS_API_KEY`. [`tools/plan.py`](tools/plan.py) writes the list of pages and clicks, and [`tools/capture.mjs`](tools/capture.mjs) drives headless Chrome through them. It waits for each comparison to finish, which takes minutes on a local model, and saves each picture here.
- **The console.** The console page runs in a browser with [`tools/console-mock.js`](tools/console-mock.js) in place of the Electron bridge. Copy `desktop/renderer/console.html` (as `index.html`), `console.css` and `console.js` into a folder, add the mock files, and load `mock-data.js`, `doctor-data.js` and `console-mock.js` before `console.js`. [`tools/console-mock-data.mjs`](tools/console-mock-data.mjs) writes the data from the console's own catalog, recipes and Doctor. Then set `CONSOLE_PREVIEW` to that folder's `file://` URL for `plan.py`.

Retake them when a screen they show changes, so the README never shows an older Lapidary than the one in the repository.
