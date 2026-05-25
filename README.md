# novel-exporter

Download novels from online novel sites (such as Syosetsu wo Yomou 小説を読もう, Kakuyomu) and
export them to EPUB, PDF, or plain text.

## Requirements

- Python 3.14 or higher
- uv

## Installation

```bash
uv sync
```

## Usage

```bash
uv run python exporter.py <url> [--format <format>] [--output-dir <directory>]
```

### Examples

Export to EPUB (default):
```bash
uv run python exporter.py https://ncode.syosetu.com/xxx/
```

The exported file can be found in `./exports/`.

Export to PDF:
```bash
uv run python exporter.py https://ncode.syosetu.com/xxx/ --format pdf
```

Export to plain text with a custom output directory:
```bash
uv run python exporter.py https://ncode.syosetu.com/xxx/ --format txt --output-dir ~/novels
```

## Supported Sources

- Syosetsu (ncode.syosetu.com, novel18.syosetu.com)

## Supported Formats

- EPUB
- PDF
- TXT

## Features

- Detects multi-chapter novels and downloads all chapters
- Staggers chapter downloads with randomized delays (30 to 60 seconds)
- Includes author name and publication date in the exported file
- Appends a source attribution section at the end of the novel

## License

MIT License

Copyright 2026 Victor Neo

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the “Software”), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
