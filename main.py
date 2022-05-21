# Copyright 2022 Andrew Chen Wang, Ur LLC
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from pathlib import Path
from time import sleep

import requests
from bs4 import BeautifulSoup


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15 "
}


def _attempt_1(soup: BeautifulSoup) -> requests.Response:
    pdf_link = (
        soup.find(text=lambda t: "Original poster PDF" in t)
        .parent.select_one("a")
        .attrs["href"]
    )
    # This single California link sends a 403, probably because of our
    # HTTP agent: https://www.dfeh.ca.gov/wp-content/uploads/sites/32/2020/10/Workplace-Discrimination-Poster_ENG.pdf
    try:
        r = requests.get(pdf_link, headers=headers)
    except requests.exceptions.SSLError:
        raise AssertionError(f"[4] SSL error for {pdf_link}")
    assert r.ok, f"[4] Failed for {r.url}"
    return r


def _attempt_2(soup: BeautifulSoup) -> requests.Response:
    link = soup.select_one("object iframe").attrs["src"]
    # Clean
    if link.startswith("/"):
        link = f"https://www.laborposters.org{link}"
    elif link.startswith("https://docs.google.com/viewer?url="):
        link = link.removeprefix("https://docs.google.com/viewer?url=").split("&")[0]
    r = requests.get(link, headers=headers)
    assert r.ok, f"[4] Failed for {r.url}"
    return r


def get_pdf(state: str, r: requests.Response):
    pdf_path = Path(f"files/{state}/{r.url.split('/')[-1]}")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        return

    soup = BeautifulSoup(r.content, "html.parser")
    for x in [_attempt_1, _attempt_2]:
        try:
            r = x(soup)
            break
        except AssertionError:
            continue
    else:
        raise AssertionError(f"[3.5] Couldn't identify valid poster link for {r.url}")

    pdf_path.write_bytes(r.content)


def main():
    # This could be made better with asyncio, but I don't want
    # crash the website's server
    r = requests.get("https://www.laborposters.org/")
    assert r.ok, f"[1] Failed for {r.url}"
    tbody = BeautifulSoup(r.text, "html.parser").select_one(".sf-al").parent.parent
    links = [
        (
            tr.select_one("a").text,
            tr.select("a")[0]["href"],
        )
        for tr in tbody.select("tr")
    ]
    for state, link in links:
        r = requests.get(link)
        assert r.ok, f"[2] Failed for {link}"
        posters = BeautifulSoup(r.text, "html.parser").select(
            ".tab-content .poster-name a"
        )
        poster_links = [a.attrs["href"] for a in posters]
        for poster_link in poster_links:
            r = requests.get(poster_link)
            assert r.ok, f"[3] Failed for {r.url}"
            get_pdf(state, r)
            sleep(0.1)  # to avoid rate limit


if __name__ == "__main__":
    main()
