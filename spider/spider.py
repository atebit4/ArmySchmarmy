import re

import scrapy
from parsel import Selector

BLOCK_TAGS = {"br", "p", "div", "li", "tr", "td", "th", "table", "h1", "h2", "h3", "h4"}


def separated_text(element):
    """Keep inline text together while separating blocks and table cells."""
    parts = [element.text or ""]
    for child in element:
        if isinstance(child.tag, str):
            if child.tag in BLOCK_TAGS:
                parts.append(" ")
            parts.append(separated_text(child))
            if child.tag in BLOCK_TAGS:
                parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts)


class Spider(scrapy.Spider):
    name = "core_rules"
    start_urls = ["https://wahapedia.ru/wh40k11ed/the-rules/core-rules/"]

    def parse(self, response):
        main = response.css("#wahMainContent")
        if not main:
            self.logger.error("Rules container not found; the page layout may have changed")
            return

        # Preserve tooltip rules before removing them from the main text.
        for tooltip in main.css(".tooltip_templates > span[id^='tooltip_content']"):
            heading = tooltip.css(".tooltip_header::text").get()
            if not heading:
                continue
            copy = Selector(text=tooltip.get())
            for header in copy.css(".tooltip_header"):
                header.root.drop_tree()
            text = re.sub(r"\s+", " ", separated_text(copy.root)).strip()
            link = tooltip.css("a::attr(href)").get()
            if text:
                yield {
                    "heading": heading.strip(),
                    "text": text,
                    "source": response.urljoin(link) if link else response.url,
                    "edition": "11th",
                }

        # Remove hidden tooltip definitions and non-content elements.
        for element in main.xpath(
            './/script | .//style | .//noscript | .//*[@id and starts-with(@id, "tooltip_content")]'
        ):
            element.root.drop_tree()

        heading = None
        fragments = []

        def section():
            text = re.sub(r"\s+", " ", "".join(fragments)).strip()
            if heading and text:
                return {"heading": heading, "text": text, "source": response.url, "edition": "11th"}
            return None

        def walk(element):
            nonlocal heading, fragments
            classes = element.get("class", "").split()
            if element.tag in {"h2", "h3"} or "abName" in classes:
                previous = section()
                if previous:
                    yield previous
                heading = re.sub(r"\s+", " ", " ".join(element.itertext())).strip()
                fragments = []
                return

            if element.text:
                fragments.append(element.text)
            for child in element:
                if isinstance(child.tag, str):
                    if child.tag in BLOCK_TAGS:
                        fragments.append(" ")
                    yield from walk(child)
                    if child.tag in BLOCK_TAGS:
                        fragments.append(" ")
                if child.tail:
                    fragments.append(child.tail)

        yield from walk(main[0].root)
        last = section()
        if last:
            yield last
