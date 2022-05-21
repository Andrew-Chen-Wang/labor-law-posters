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

"""
Each state has their own labor law posters, so we need
to download them and send them to our employees to abide by the law.
"""

import asyncio
from datetime import datetime
from pathlib import Path

import aiofiles
from aiofiles import os
from aiohttp import ClientSession
from bs4 import BeautifulSoup


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15 "
}


async def _attempt_1(session, soup: BeautifulSoup) -> bytes:
    pdf_link = (
        soup.find(text=lambda t: "Original poster PDF" in t)
        .parent.select_one("a")
        .attrs["href"]
    )
    # This single California link sends a 403, probably because of our
    # HTTP agent: https://www.dfeh.ca.gov/wp-content/uploads/sites/32/2020/10/Workplace-Discrimination-Poster_ENG.pdf
    async with session.get(pdf_link) as r:
        assert r.ok, f"[4a] Failed for {r.url}"
        return await r.read()


async def _attempt_2(session, soup: BeautifulSoup) -> bytes:
    link = soup.select_one("object iframe").attrs["src"]
    # Clean
    if link.startswith("/"):
        link = f"https://www.laborposters.org{link}"
    elif link.startswith("https://docs.google.com/viewer?url="):
        link = link.removeprefix("https://docs.google.com/viewer?url=").split("&")[0]
    # Run
    async with session.get(link) as r:
        assert r.ok, f"[4b] Failed for {r.url}"
        return await r.read()


async def get_pdf(session, state: str, text: str, original_url: str):
    file = f"files/{state}/{original_url.split('/')[-1]}"
    if await os.path.exists(file):
        return

    soup = BeautifulSoup(text, "html.parser")
    errors = []
    for i, x in enumerate([_attempt_1, _attempt_2]):
        try:
            r = await x(session, soup)
            async with aiofiles.open(file, "wb") as f:
                await f.write(r)
            break
        except BaseException as e:
            errors.append(f"Attempt {i} for {original_url}. Error:\n{e}")
            continue
    else:
        print(f"Errors for attempt:")
        for e in errors:
            print(e)
        raise AssertionError(
            f"[3.5] Couldn't identify valid poster link for {original_url}"
        )


async def get_poster(session, state, link):
    async with session.get(link) as r:
        assert r.ok, f"[3] Failed for {r.url}"
        content = await r.text()
    await get_pdf(session, state, content, link)


async def main(session, state, link):
    async with session.get(link) as r:
        assert r.ok, f"[2] Failed for {link}"
        posters = BeautifulSoup(await r.text(), "html.parser").select(
            ".tab-content .poster-name a"
        )
    poster_links = [a.attrs["href"] for a in posters]
    tasks = []
    for poster_link in poster_links:
        tasks.append(
            asyncio.create_task(get_poster(session, state, poster_link))
        )
    await asyncio.gather(*tasks)


async def begin():
    async with ClientSession(headers=headers) as session:
        async with session.get("https://www.laborposters.org/") as r:
            assert r.ok, f"[1] Failed for {r.url}"
            text = await r.text()
        tbody = BeautifulSoup(text, "html.parser").select_one(".sf-al").parent.parent
        links = [
            (
                tr.select_one("a").text,
                tr.select("a")[0]["href"],
            )
            for tr in tbody.select("tr")
        ]
        for state, _ in links:
            pdf_path = Path(f"files/{state}/")
            pdf_path.mkdir(parents=True, exist_ok=True)

        await asyncio.gather(
            *[main(session, state, link) for state, link in links]
        )


if __name__ == "__main__":
    print(f"Starting download at {datetime.now()}")
    Path("files").mkdir(parents=True, exist_ok=True)
    _loop = asyncio.get_event_loop()
    _loop.run_until_complete(begin())
    print(f"Finished download at {datetime.now()}")
