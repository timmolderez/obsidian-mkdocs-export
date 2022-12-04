import logging
import os
import pathlib
import re
import shutil
from functools import partial
from typing import Optional, List, Match

import fire

from obsidian_mkdocs.utils import (
    MDLINK_RE,
    WIKILINK_RE,
    wiki_match_to_link,
    md_match_to_link,
    render_link,
    render_image_link,
    find_linked_file,
    markdown_fix_blank_lines,
)


def export_obsidian_to_mkdocs(
    vault_path: str,
    output_path: str,
    starting_note: Optional[str],
):
    wiki_path = os.path.join(output_path, "./wiki")
    if os.path.exists(wiki_path):
        shutil.rmtree(wiki_path)
    os.makedirs(wiki_path, exist_ok=True)

    # Process the starting note, and everything reachable from it
    process_file(starting_note, vault_path, wiki_path, [])

    # Generate the MkDocs site
    config_file = os.path.join(output_path, "mkdocs.yml")
    if not os.path.exists(config_file):
        config_template = os.path.join(
            os.path.dirname(__file__), "../mkdocs_default.yml"
        )
        shutil.copyfile(config_template, config_file)
    os.chdir(output_path)
    os.system("mkdocs build")


def process_file(
    file_path: str, vault_path: str, output_path: str, visited_files: List[str]
) -> List[str]:
    visited_files.append(file_path)

    abs_file_path = os.path.join(vault_path, file_path)
    with open(abs_file_path, "r", encoding="utf-8") as in_file:
        contents = in_file.read()
        contents = markdown_fix_blank_lines(contents)

        # Replace all links in this file to the MkDocs-compatible format
        # The calls to `process_link` have two side-effects!
        # - All files reachable via each link are processed (the recursive step)
        # - The visited_files list is updated accordingly
        contents = re.sub(
            MDLINK_RE,
            partial(
                process_link,
                vault_path,
                file_path,
                output_path,
                visited_files,
                False,
            ),
            contents,
        )
        contents = re.sub(
            WIKILINK_RE,
            partial(
                process_link,
                vault_path,
                file_path,
                output_path,
                visited_files,
                True,
            ),
            contents,
        )

        out = os.path.join(output_path, file_path)
        with open(out, "w", encoding="utf-8") as out_file:
            out_file.write(contents)
    return visited_files


def process_link(
    vault_path: str,
    parent_path: str,
    output_path: str,
    visited_files: List[str],
    is_wiki: bool,
    match: Match,
) -> str:
    link = wiki_match_to_link(match) if is_wiki else md_match_to_link(match)

    # Don't need to do anything special for links with e.g. https://, file://
    if "://" in link.path:
        return render_link(link)

    file_path = find_linked_file(link.path, parent_path, vault_path)
    if not file_path:
        logging.warning(f"Could not find file for link {link.path}")
        link.alias = link.path + " -file not found-"
        return render_link(link)

    parent_dir = os.path.dirname(parent_path)

    rel_path = os.path.relpath(file_path, parent_dir)
    rel_path = pathlib.Path(rel_path).as_posix()  # MkDocs needs Posix paths
    abs_path = os.path.join(vault_path, file_path)
    out_abs_path = os.path.join(output_path, file_path)
    out_abs_dir = os.path.dirname(out_abs_path)

    rendered_link = None
    img_exts = [".jpg", ".gif", ".png", ".svg"]

    if any([file_path.endswith(ext) for ext in img_exts]):
        link.path = rel_path
        rendered_link = render_image_link(link)
    else:
        if not link.alias:
            link.alias = link.path
        link.path = rel_path
        rendered_link = render_link(link)
    # TODO convert Excalidraw images

    if file_path not in visited_files:
        os.makedirs(out_abs_dir, exist_ok=True)
        shutil.copyfile(abs_path, out_abs_path)
        if file_path.endswith(".md"):
            # Do the recursive step
            process_file(file_path, vault_path, output_path, visited_files)

    return rendered_link


if __name__ == "__main__":
    fire.Fire(export_obsidian_to_mkdocs)
