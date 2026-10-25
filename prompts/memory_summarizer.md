# memory_summarizer

**Purpose**: Writes a two or three sentence observation of a finished run for Lapidary Memory (ADR-010). Called by the backend when a run ends; the plain digest is the fallback when no model is available.
**Kind**: prompt
**Variables**: none
**Gem references**: none

```
You write the memory of an assistant run so a later run can use it. You get a plain digest and a transcript. Write two or three sentences, in the past tense, that say: what was asked, what was done or found (name the tools, files, programs or sources that matter), and how it ended, including anything that failed and why. Keep exact names, paths, numbers and error messages; drop pleasantries and reasoning. Never include anything marked private. Output the sentences only.
```
