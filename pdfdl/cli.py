import os
import re
import argparse
import platform
from urllib.parse import urljoin, urlparse, unquote
from collections import deque
from importlib.metadata import version as get_installed_version, PackageNotFoundError
import requests
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm
from colorama import init, Fore, Style


# Initialize colorama
init(autoreset=True)
UNDERLINE = "\033[4m"
RESET = Style.RESET_ALL


# User-Agent detection based on OS
def get_default_user_agent():
    system = platform.system()
    if system == "Darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.3.1 Safari/605.1.15"
        )
    elif system == "Linux":
        return "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1"
    return ("Mozilla/5.0Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0")


# Print helpers
def print_info(msg):
    print(f"{Style.BRIGHT}{Fore.CYAN}[*]{Style.RESET_ALL} {msg}")


def print_warn(msg):
    print(f"{Style.BRIGHT}{Fore.YELLOW}[!]{Style.RESET_ALL} {msg}")


def print_error(msg):
    print(f"{Style.BRIGHT}{Fore.RED}[!]{Style.RESET_ALL} {msg}")


def print_success(msg):
    print(f"{Style.BRIGHT}{Fore.GREEN}[+]{Style.RESET_ALL} {msg}")


def get_installed_version_safe(pkg_name: str) -> str:
    try:
        return get_installed_version(pkg_name)
    except PackageNotFoundError:
        return "(version unknown)"


def download_file(
    response: requests.Response, filename: str, output_dir: str, overwrite: bool
):
    os.makedirs(output_dir, exist_ok=True)
    full_path = os.path.join(output_dir, filename)

    if not overwrite and os.path.exists(full_path):
        print_warn(
            f"File '{full_path}' already exists. Use --overwrite to replace it. Skipping."
        )
        return

    total_size = int(response.headers.get("content-length", 0))
    print_info(f"Downloading to '{full_path}'...")
    try:
        with open(full_path, "wb") as f, tqdm(
            desc=f"      {filename}",
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    size = f.write(chunk)
                    bar.update(size)
        print_success(f"Successfully downloaded '{full_path}'")
    except OSError as e:
        print_error(
            f"OS Error downloading to '{full_path}'. It may have an invalid name. Error: {e}"
        )


def get_filename_from_response(response: requests.Response) -> str:
    content_disposition = response.headers.get("content-disposition")
    filename = None
    if content_disposition:
        fname_star_match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
        if fname_star_match:
            filename = fname_star_match.group(1)
        else:
            fname_match = re.search(r"filename=([^;]+)", content_disposition)
            if fname_match:
                filename = fname_match.group(1).strip("\"'")

    if not filename:
        path = urlparse(response.url).path
        filename = os.path.basename(path).split("?")[0] or "downloaded.pdf"

    return re.sub(r'[<>:"/\\|?*]', "_", unquote(filename))


def resolve_final_url(url: str, headers: dict) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
        return response.url
    except requests.RequestException:
        return url


def process_url_queue(
    urls_to_process: list, output_dir: str, overwrite: bool, user_agent: str
):
    queue = deque(urls_to_process)
    visited_urls = set()
    headers = {"User-Agent": user_agent}

    article_view_pattern = re.compile(
        r"/([^/]+)/article/view/(\d+)(?:/(\d+))"
    )

    while queue:
        current_url = queue.popleft()

        if not current_url or current_url in visited_urls:
            continue

        # Check for /<journal>/article/view/<submission_ID>/<upload_ID>/ pattern
        match = article_view_pattern.search(current_url)
        tried_download = False
        if match:
            journal, submission_id, upload_id = match.groups()
            # Try /article/download/ first
            download_url = current_url.replace(
                "/article/view/", "/article/download/"
            )

            resolved_download_url = resolve_final_url(download_url, headers)
            print(
                f"\n{Style.BRIGHT}{Fore.YELLOW}--- Trying direct download: {UNDERLINE}{resolved_download_url}{RESET} ---"
            )
            try:
                with requests.get(
                    resolved_download_url,
                    stream=True,
                    timeout=30,
                    allow_redirects=True,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "application/pdf" in content_type:
                        filename = get_filename_from_response(response)
                        download_file(response, filename, output_dir, overwrite)
                        visited_urls.add(resolved_download_url)
                        tried_download = True
                        print_success("Direct download succeeded.")
                        continue  # Skip further processing for this URL
            except Exception as e:
                print_warn(f"Direct download attempt failed: {e}")

        resolved_url = resolve_final_url(current_url, headers)
        print(
            f"\n{Style.BRIGHT}{Fore.YELLOW}--- Processing: {UNDERLINE}{resolved_url}{RESET} ---"
        )
        visited_urls.add(resolved_url)

        try:
            with requests.get(
                resolved_url,
                stream=True,
                timeout=30,
                allow_redirects=True,
                headers=headers,
            ) as response:
                response.raise_for_status()
                final_url = response.url
                content_type = response.headers.get("content-type", "").lower()

                if "application/pdf" in content_type:
                    print_info("Response is a direct PDF file.")
                    filename = get_filename_from_response(response)
                    download_file(response, filename, output_dir, overwrite)
                    continue

                elif "text/html" in content_type:
                    links = []
                    print_info("Response is an HTML page. Scanning for links...")
                    soup = BeautifulSoup(response.text, "html.parser")
                    found_links = False
                    for link_tag in soup.find_all("a", href=True):
                        if not isinstance(link_tag, Tag):
                            continue
                        href = link_tag.get("href")
                        if isinstance(href, list):
                            href = "".join(href)
                        if not isinstance(href, str):
                            continue  # Skip if href is not a string
                        link_class = link_tag.get("class")
                        if not link_class:
                            link_class = []
                        has_download_attr = link_tag.has_attr("download")

                        absolute_link = urljoin(final_url, href)

                        if "download" in link_class and has_download_attr:
                            absolute_link = resolve_final_url(absolute_link, headers)
                            if absolute_link not in visited_urls:
                                print_info(
                                    f"Direct PDF link found: {UNDERLINE}{absolute_link}{RESET}"
                                )
                                try:
                                    pdf_response = requests.get(
                                        absolute_link,
                                        stream=True,
                                        timeout=30,
                                        headers=headers,
                                    )
                                    pdf_response.raise_for_status()
                                    filename = get_filename_from_response(pdf_response)
                                    download_file(
                                        pdf_response, filename, output_dir, overwrite
                                    )
                                    found_links = True
                                except Exception as e:
                                    print_error(
                                        f"Failed to download from {absolute_link}: {e}"
                                    )
                        elif "pdf" in link_class or href.lower().endswith(".pdf"):
                            if (
                                absolute_link not in visited_urls
                                and absolute_link not in queue
                            ):
                                links.append(absolute_link)
                                found_links = True
                    queue = deque(links) + queue  # Prioritize new links

                    if not found_links:
                        print_warn("No new PDF links found on this page.")
                else:
                    print_warn(f"Unhandled content type '{content_type}'. Skipping.")

        except requests.exceptions.RequestException as e:
            print_error(
                f"A network error occurred for {UNDERLINE}{resolved_url}{RESET}: {e}"
            )
        except Exception as e:
            print_error(
                f"An unexpected error occurred while processing {UNDERLINE}{resolved_url}{RESET}: {e}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Intelligently crawl web pages to find and download PDF files.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s https://example.com/articles -o downloads\n"
            "  %(prog)s -i url_list.txt --overwrite\n"
            "  %(prog)s https://example.com/view/123 -o ./pdfs --overwrite"
        ),
    )
    parser.add_argument(
        "urls", metavar="URL", nargs="*", help="One or more starting URLs."
    )
    parser.add_argument(
        "-i",
        "--input-file",
        help="Path to a text file with starting URLs (one per line).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Directory to save the downloaded PDF files.",
    )
    parser.add_argument(
        "--user-agent",
        default=get_default_user_agent(),
        help="Custom User-Agent string for HTTP requests.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files if they already exist.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {get_installed_version_safe('pdfdl')}",
    )
    args = parser.parse_args()
    start_urls = []

    if args.input_file:
        print_info(f"Reading URLs from file: {UNDERLINE}{args.input_file}{RESET}")
        try:
            with open(args.input_file, "r") as f:
                start_urls.extend([line.strip() for line in f if line.strip()])
        except FileNotFoundError:
            print_error(f"Input file not found at '{args.input_file}'")
            return

    start_urls.extend(args.urls)

    if not start_urls:
        print_warn("No starting URLs provided.")
        parser.print_help()
        return

    process_url_queue(start_urls, args.output_dir, args.overwrite, args.user_agent)
    print_success("All processing complete.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warn("\nInterrupted by user. Exiting...")
