import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pprint import pprint
from typing import Optional, Match

# Markdown link regex - Match groups are:
#       0: Everything: [alias](path#anchor)
#       1: alias
#       2: path#anchor
#       3: path
#       4. #anchor
MDLINK_RE = r"\[([^\]]+)\]\((([^)/]+)(#.*)*)\)"

# Wikilink regex - Match groups are:
#       0: Everything: [[path#anchor|alias]]
#       1: path#anchor|alias
#       2: path
#       3: #anchor
#       4: |alias
WIKILINK_RE = r"\[\[(([^\]#\|]*)(#[^\|\]]+)?(\|[^\]]*?)?)\]\]"


@dataclass
class Link:
    path: str
    alias: Optional[str]
    anchor: Optional[str]


def md_match_to_link(match: Match) -> Link:
    anchor = match.group(3)
    anchor = anchor[1:] if anchor else None
    return Link(path=match.group(3), alias=match.group(1), anchor=anchor)


def wiki_match_to_link(match: Match) -> Link:
    alias = match.group(4)
    alias = alias[1:] if alias else None
    anchor = match.group(3)
    anchor = anchor[1:] if anchor else None
    return Link(
        path=match.group(2),
        alias=alias,
        anchor=anchor,
    )


def render_link(l: Link) -> str:
    anchor = f"#{l.anchor}" if l.anchor else ""
    alias = (
        l.alias
        if l.alias
        else (l.path[:-3] if l.path.endswith(".md") else l.path)
    )
    return f"[{alias}]({l.path}{anchor})"


def render_image_link(l: Link) -> str:
    # [Image title](https://dummyimage.com/600x400/){ width="300" }
    # https://squidfunk.github.io/mkdocs-material/reference/images/

    anchor = f"#{l.anchor}" if l.anchor else ""

    img_size = l.alias if (l.alias and l.alias.isnumeric()) else None
    img_attr = f'{{width="{img_size}"}}' if img_size else ""

    alias = l.alias if (l.alias and not img_size) else l.path

    return f"[{alias}]({l.path}{anchor}){img_attr}"


def find_linked_file(
    link_path: str, parent_path: str, vault_path: str
) -> Optional[str]:
    link_format = vault_link_format(vault_path)

    final_path = None
    if link_format == "absolute":
        final_path = checked_path(link_path, vault_path)
    if link_format == "relative":
        final_path = checked_path(
            os.path.join(parent_path, link_path), vault_path
        )
    if link_format == "shortest":
        if "/" in link_path:  # Must be identical to "absolute" then
            final_path = checked_path(link_path, vault_path)
        else:  # Otherwise it may have been shortened
            rel_path = find_file(link_path + ".md", vault_path)
            if not rel_path:
                rel_path = find_file(link_path, vault_path)
            if rel_path:
                final_path = checked_path(rel_path, vault_path)
    return final_path


def find_file(name: str, path: str) -> Optional[str]:
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)


def checked_path(file_path: str, vault_path: str) -> Optional[str]:
    abs_path = os.path.join(vault_path, file_path + ".md")
    if os.path.exists(abs_path):
        return file_path + ".md"

    abs_path = os.path.join(vault_path, file_path)
    if os.path.exists(abs_path):
        return file_path

    return None


@lru_cache
def vault_link_format(vault_path: str) -> str:
    """
    Returns "New link format" vault setting:
    - "shortest" : just the note name if possible; path relative to the vault
        root otherwise (this is the default setting)
    - "relative" : link is a path relative to the current file
    - "absolute": always a path relative to the vault root
    """
    vault_config_file = os.path.join(vault_path, "./.obsidian/app.json")
    with open(vault_config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        return config.get("newLinkFormat", "shortest")


# Markdown lines with a list (or table) element
MD_LIST_RE = r"^((\d+\. )|((-|\*|\+|\|) ))"


def markdown_fix_blank_lines(content: str):
    """
    Strict Markdown requires that lists and tables are surrounded by a blank
    line. This function makes sure that's always the case, because Obsidian
    doesn't have this requirement.
    """

    lines = content.splitlines(keepends=True)
    new_text = ""
    in_list = False
    was_in_list = False

    for line in lines:
        sline = line.lstrip()

        was_in_list = in_list  # Were we in a list on the previous line
        in_list = bool(re.search(MD_LIST_RE, sline, flags=re.MULTILINE))

        if not was_in_list and in_list:  # Start of list
            line = "\n" + line
        elif was_in_list and not in_list:  # End of list
            line = "\n" + line

        new_text += line
    return new_text


def extract_json_from_excalidraw_md(file_path: str) -> str:
    in_json = False
    json_contents = ""
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f.readlines():
            if line == "```json\n":
                in_json = True
            elif line == "```\n":
                in_json = False
            else:
                if in_json:
                    json_contents += line

    out_path = file_path[:-3]
    with open(file_path[:-3], "w") as out_f:
        out_f.write(json_contents)

    return out_path
