# Translator requests (base prompts; the api subcommand adds the TERM MEMORY block at send time)

`requests.jsonl` has 405 rows: system, user (base prompt without term memory), prompt_sha256 of that base prompt, targets. The row written to `renderings_<model>.jsonl` carries `prompt_sha256` of the prompt actually sent (base + memory) and `term_memory`, so the sent prompt is reconstructable from these two files.

Session path (cycle 1, no API): for every row act exactly as `system` says on `user`; write one JSON object per line to `responses_<model>.jsonl` with unit_id, model, started_utc, finished_utc, response (the object the system prompt asks for). Do not read any other file; no glossary; no skipping.
