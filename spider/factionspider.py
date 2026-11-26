"""Extract Wahapedia faction detachments into grouped JSON records.
Run from the repository root:
    scrapy runspider spider/factionspider.py -a url=URL -a faction="Faction name" -O faction.json
"""

import re
from urllib.parse import urldefrag, urlparse

import scrapy
from parsel import Selector

BLOCKS = {"br", "p", "div", "li", "tr", "td", "th", "table", "h1", "h2", "h3", "h4"}


def text_content(element):
    """Separate block elements while preserving spaces within inline text."""
    parts = [element.text or ""]
    for child in element:
        if isinstance(child.tag, str):
            if child.tag in BLOCKS:
                parts.append(" ")
            parts.append(text_content(child))
            if child.tag in BLOCKS:
                parts.append(" ")
        parts.append(child.tail or "")
    return " ".join("".join(parts).split())


def cleaned_text(selector):
    if not selector:
        return ""
    copy = Selector(text=selector.get())
    for node in copy.css("script, style, .ShowFluff, .faqErrataSpoiler, .tooltip_templates"):
        node.root.drop_tree()
    return text_content(copy.root)


def tooltip_records(main, response, faction, edition, seen):
    for tooltip in main.css(".tooltip_templates > span[id^='tooltip_content']"):
        heading = tooltip.css(".tooltip_header::text").get()
        if not heading:
            continue
        copy = Selector(text=tooltip.get())
        for header in copy.css(".tooltip_header"):
            header.root.drop_tree()
        text = text_content(copy.root)
        if text:
            link = tooltip.css("a::attr(href)").get()
            source = response.urljoin(link) if link else response.url
            key = (heading.strip(), text, source)
            if key in seen:
                continue
            seen.add(key)
            yield {"kind": "tooltip", "faction": faction, "edition": edition,
                   "name": heading.strip(), "source": source,
                   "text": text}


class FactionSpider(scrapy.Spider):
    name = "wahapedia_faction"
    custom_settings = {"ROBOTSTXT_OBEY": True, "DOWNLOAD_DELAY": 1}

    def __init__(self, url=None, faction=None, chapter=None, edition="11th", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not url or not faction:
            raise ValueError('Provide -a url=URL and -a faction="Faction name"')
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"wahapedia.ru", "www.wahapedia.ru"}:
            raise ValueError("This spider only supports Wahapedia URLs")
        self.start_urls = [url]
        self.faction = faction
        self.chapter = chapter
        self.edition = edition
        self.seen_tooltips = set()

    def parse(self, response):
        main = response.css("#wahMainContent")
        if not main:
            self.logger.error("Faction content not found; the page layout may have changed")
            return

        yield from tooltip_records(main, response, self.faction, self.edition, self.seen_tooltips)

        # Retain the faction page itself, including army rules and other modes.
        # It is separate from structured detachments so no page content is silently lost.
        page = Selector(text=main.get())
        for node in page.css("script, style, .tooltip_templates, .contentsWrap, .FiltersMultiOuter"):
            node.root.drop_tree()
        yield {
            "kind": "faction_page",
            "faction": self.faction,
            "chapter_context": self.chapter,
            "edition": self.edition,
            "source": response.url,
            "text": text_content(page.root),
        }

        # Follow individual pages within this faction only; do not crawl other factions.
        path = urlparse(response.url).path
        match = re.match(r"^(/[^/]+/factions/[^/]+/)", path)
        if not match:
            self.logger.error("Cannot identify the faction path in %s", response.url)
            return
        base_path = match.group(1)
        unit_urls = set()
        for href in main.css("a::attr(href)").getall():
            url = urldefrag(response.urljoin(href)).url
            parsed = urlparse(url)
            remaining = parsed.path[len(base_path):] if parsed.path.startswith(base_path) else ""
            if (parsed.hostname == urlparse(response.url).hostname and remaining and url.rstrip("/") != response.url.rstrip("/")
                    and "/" not in remaining.strip("/") and not parsed.query
                    and not re.search(r"\.(?:html?|php|png|jpe?g|gif|svg|pdf|css|js)$", remaining, re.I)):
                unit_urls.add(url)
        for url in sorted(unit_urls):
            yield response.follow(url, callback=self.parse_unit)

        count = 0
        for heading in main.css("h2.outline_header"):
            container = heading.xpath("..")
            if "clFl" not in container.attrib.get("class", "").split():
                continue
            if not container.css("h2[id^='Detachment-Rule']"):
                continue
            # The detachment title has a separate points badge; leave it out of the name.
            name = " ".join(heading.xpath("./text()").getall()).strip()
            name = re.sub(r"\s+", " ", name)
            if not name:
                self.logger.warning("Skipped detachment with no readable name")
                continue

            rule_title = container.xpath(
                './/h2[starts-with(@id, "Detachment-Rule")]/parent::*/following-sibling::*//h3[@id][1]'
            ).getall()
            rule = None
            if rule_title:
                title = Selector(text=rule_title[0]).css("h3")
                rule_id = title.attrib.get("id")
                original = container.xpath('.//h3[@id=$id]', id=rule_id)[0]
                rule = {"name": cleaned_text(original), "text": cleaned_text(original.xpath(".."))}

            enhancements = []
            for cell in container.css("td.td_w:has(ul.EnhancementsPts)"):
                spans = cell.css("ul.EnhancementsPts li span::text").getall()
                if spans:
                    enhancements.append({"name": spans[0].strip(), "points": spans[1].strip() if len(spans) > 1 else None, "text": cleaned_text(cell)})

            stratagems = []
            for card in container.css(".str11Wrap"):
                name_element = card.css(".str11Name")
                if name_element:
                    stratagems.append({"name": cleaned_text(name_element), "cost": cleaned_text(card.css(".str11CP")), "text": cleaned_text(card.css(".str11Text"))})

            updates = []
            for update in container.css(".faqErrataSpoiler"):
                title = cleaned_text(update.css(".faqErrataHead h3"))
                body = cleaned_text(update.css(".faqErrataSpoilerBody"))
                if body:
                    updates.append({"type": title or "FAQ / Errata", "text": body})

            count += 1
            yield {
                "kind": "detachment",
                "faction": self.faction,
                "chapter_context": self.chapter,
                "edition": self.edition,
                "detachment": name,
                "source_books": heading.css("img.logo3_11::attr(title)").getall(),
                "eligibility": "not_evaluated",
                "source": response.urljoin("#" + heading.attrib.get("id", "")),
                "detachment_rule": rule,
                "enhancements": enhancements,
                "stratagems": stratagems,
                "faq_errata": updates,
            }
        if not count:
            self.logger.warning("No detachments found; check the URL and page layout")

    def parse_unit(self, response):
        main = response.css("#wahMainContent")
        datasheets = main.css(".datasheet")
        if not datasheets:
            self.logger.warning("No datasheet found at %s", response.url)
            return
        yield from tooltip_records(main, response, self.faction, self.edition, self.seen_tooltips)
        for datasheet in datasheets:
            keywords = {}
            for node in datasheet.xpath('.//*[text()[contains(., "KEYWORDS:")]]'):
                value = cleaned_text(node)
                label, separator, contents = value.partition(":")
                if separator and label.strip() in {"KEYWORDS", "FACTION KEYWORDS"}:
                    keywords[label.strip().lower().replace(" ", "_")] = [s.strip() for s in contents.split(";") if s.strip()]
            tables = []
            for table in datasheet.css("table"):
                rows = [[cleaned_text(cell) for cell in row.xpath("./th | ./td")]
                        for row in table.css("tr")]
                rows = [row for row in rows if any(row)]
                if rows:
                    tables.append(rows)
            yield {
                "kind": "datasheet",
                "faction": self.faction,
                "chapter_context": self.chapter,
                "edition": self.edition,
                "name": (response.css("title::text").get() or "").split(" — ")[0].strip(),
                "source": response.url,
                "text": cleaned_text(datasheet),
                "keywords": keywords,
                "tables": tables,
                "eligibility": "not_evaluated",
                "faq_errata": [cleaned_text(update.css(".faqErrataSpoilerBody"))
                               for update in datasheet.css(".faqErrataSpoiler")
                               if update.css(".faqErrataSpoilerBody")],
            }
