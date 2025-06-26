# pdfdl — Intelligent PDF Downloader

`pdfdl` is a Python command-line tool to intelligently crawl academic or article-based websites and download PDF files. It supports redirects, content detection, and queue-based crawling of PDF viewer pages.

_It only works on journals built with [OJS](https://pkp.sfu.ca/software/ojs/) for now._

## Features

- Detects direct PDF links and downloads them.
- Parses HTML pages to discover viewer or download links (e.g., `<a class="pdf">`, `<a class="download" download>`).
- Follows redirects and resolves final URLs before adding them to the queue.
- Automatically decodes filenames from headers or URLs.
- Supports custom User-Agent strings.

## Installation

To install from a local folder:

```bash
git clone https://github.com/itsKhalidHossain/pdfdl.git
cd pdfdl
pip install .
````

Or to install from GitHub:

```bash
pip install git+https://github.com/itsKhalidHossain/pdfdl.git
```

## Usage

```bash
pdfdl [OPTIONS] [URL ...]
```

### Common Options

| Option             | Description                                           |
| ------------------ | ----------------------------------------------------- |
| `-i, --input-file` | Read URLs from a file (one per line)                  |
| `-o, --output-dir` | Directory to save downloaded files (default: current) |
| `--overwrite`      | Overwrite existing files                              |
| `--user-agent`     | Use a custom User-Agent string                        |
| `-v, --version`    | Show the version number and exit                      |
| `-h, --help`       | Show help message and exit                            |

### Examples

```bash
# Download all PDFs from a journal issue
pdfdl https://example.com/journal/issue/view/12 -o papers/

# Download a single article PDF
pdfdl https://example.com/journal/article/view/42

# Download a from a list 
pdfdl -i url_list.txt

# Use a custom user agent
pdfdl -o downloads/ --user-agent "MyBot/1.0" https://example.com
```

## Requirements

* Python 3.8+
* Dependencies:

  * `requests`
  * `beautifulsoup4`
  * `tqdm`
  * `colorama`

Install them with:

```bash
pip install -r requirements.txt
```

Or automatically via pip if you use the package.

## License

MIT License

---

**Developed by Khalid Hossain**

Contributions welcome! 😊
