# Cloud tests

These tests call remote LLM APIs and may consume tokens. They are not part of the default suite.

Run from the repository root (see `.ai/local/python_path.txt` for the interpreter path):

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/cloud -q -m cloud
```

`DASHSCOPE_API_KEY` must be set in the environment (or in a project `.env` file that is not committed).
