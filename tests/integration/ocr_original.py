# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic raster evidence; OCR expectation is authored independently."""
from io import BytesIO
import re
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path

PHRASE='SCANNED SAFETY KEY K17'


def scanned_original():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,NumberObject
    with TemporaryDirectory() as directory:
        root=Path(directory); writer=PdfWriter(); page=writer.add_blank_page(width=612,height=792)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject(); stream.set_data(('BT /F1 24 Tf 36 700 Td ('+PHRASE+') Tj ET').encode())
        page[NameObject('/Contents')]=writer._add_object(stream); writer.write(root/'printed.pdf')
        rendered=subprocess.run(['/usr/bin/pdftoppm','-gray','-r','150','-singlefile',str(root/'printed.pdf')],capture_output=True,timeout=10)
        assert rendered.returncode==0
        match=re.match(rb'P5\s+(\d+)\s+(\d+)\s+255\s',rendered.stdout)
        assert match is not None
        width,height=map(int,match.groups()); image=rendered.stdout[match.end():]
        assert len(image)==width*height
        writer=PdfWriter(); page=writer.add_blank_page(width=612,height=792)
        raster=DecodedStreamObject(); raster.set_data(image)
        raster.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),
            NameObject('/Width'):NumberObject(width),NameObject('/Height'):NumberObject(height),
            NameObject('/ColorSpace'):NameObject('/DeviceGray'),NameObject('/BitsPerComponent'):NumberObject(8)})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im0'):writer._add_object(raster.flate_encode())})})
        stream=DecodedStreamObject(); stream.set_data(b'q 612 0 0 792 0 0 cm /Im0 Do Q')
        page[NameObject('/Contents')]=writer._add_object(stream)
        output=BytesIO(); writer.write(output); return output.getvalue()
