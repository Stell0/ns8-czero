# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Rebuild public synthetic M0 originals; no C0 service or network is used."""
from datetime import datetime
from pathlib import Path
import zipfile

from docx import Document
from docx.enum.section import WD_SECTION_START
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def pdf(path, pages):
    writer = PdfWriter()
    for label in pages:
        page = writer.add_blank_page(width=612, height=792)
        resources = DictionaryObject()
        content = DecodedStreamObject()
        if label == "SCAN":
            image = DecodedStreamObject()
            image.set_data(b"\x00\xff\x00\xff")
            image.update({NameObject("/Type"): NameObject("/XObject"),
                          NameObject("/Subtype"): NameObject("/Image"),
                          NameObject("/Width"): NumberObject(2),
                          NameObject("/Height"): NumberObject(2),
                          NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                          NameObject("/BitsPerComponent"): NumberObject(8)})
            resources[NameObject("/XObject")] = DictionaryObject({
                NameObject("/Im0"): writer._add_object(image)})
            content.set_data(b"q 100 0 0 100 72 600 cm /Im0 Do Q")
        elif label:
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            resources[NameObject("/Font")] = DictionaryObject({
                NameObject("/F1"): writer._add_object(font)})
            content.set_data(f"BT /F1 12 Tf 72 720 Td ({label}) Tj ET".encode("ascii"))
        else:
            content.set_data(b"")
        page[NameObject("/Resources")] = writer._add_object(resources)
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(path)


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    pdf(destination / "readable-100.pdf", [f"Page {i:03d}: synthetic evidence {i:03d}." for i in range(1, 101)])
    pdf(destination / "mixed-scan.pdf", ["Page 001: readable evidence.", "SCAN"])
    pdf(destination / "blank-pages.pdf", [None, "Page 002: first evidence.", None,
                                          "Page 004: last evidence.", None])
    pdf(destination / "all-blank.pdf", [None, None])
    document = Document()
    document.core_properties.created = document.core_properties.modified = datetime(2026, 1, 1)
    document.core_properties.author = "C0 synthetic fixture"
    document.add_heading("Section One", level=1)
    document.add_paragraph("Body café 東京.")
    table = document.add_table(rows=2, cols=2)
    for cell, label in zip((c for row in table.rows for c in row.cells),
                           ["Asset", "State", "Example server", "Ready"]):
        cell.text = label
    document.sections[0].header.paragraphs[0].text = "Header One"
    document.sections[0].footer.paragraphs[0].text = "Footer One"
    section = document.add_section(WD_SECTION_START.NEW_PAGE)
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    section.header.paragraphs[0].text = "Header Two"
    section.footer.paragraphs[0].text = "Footer Two"
    document.add_heading("Section Two", level=1)
    document.add_paragraph("Last body paragraph.")
    path = destination / "structured.docx"
    document.save(path)
    # python-docx's ZIP timestamps otherwise depend on wall-clock time.
    with zipfile.ZipFile(path) as archive:
        entries = [(item.filename, archive.read(item)) for item in archive.infolist()]
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in sorted(entries):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, body)
    (destination / "fenced.md").write_bytes(
        b"\xef\xbb\xbf# Real heading\r\n\r\n" + "café 東京 [reference](#last).".encode() +
        b"\r\n\r\n```text\r\n# Fenced heading\r\nliteral body\r\n```\r\n\r\n## Last\r\nEnd.\r\n")
    (destination / "plain.txt").write_bytes("First café 東京.\r\n\r\nLast line.\r".encode())
    # Existing project publisher creates the logical parent and its receipts.
    # This body deliberately crosses the legacy 128 KiB publication-part bound.
    (destination / "multipart.md").write_text(
        "# Synthetic multipart manual\n\n" + "".join(
            f"Paragraph {i:04d}: café 東京 evidence.\n\n" for i in range(4000)), encoding="utf-8")


if __name__ == "__main__":
    import sys
    generate(Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).parent)
