"""Shared by the leak gate (leak-scan, semantic-review, strip-metadata): find the files under some
paths and pull out every piece of text a reader of the published file could get at.

Text files are read as they are. EPUBs are opened and each text member read. PDFs go through
pdftotext, and their document metadata through pdfinfo. Images contribute their metadata (EXIF,
PNG text chunks, comments) as text, and report whether they carry a GPS position.
Anything that cannot be read raises GateError: the gate fails closed, never skips silently.
"""
import io
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff"}
GPS_IFD = 0x8825


class GateError(Exception):
    pass


def files_under(paths):
    for p in map(Path, paths):
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from (f for f in sorted(p.rglob("*")) if f.is_file() and ".git" not in f.parts)
        else:
            raise GateError(f"no such file: {p}")


def _is_binary(data):
    return b"\0" in data[:8192]


def _pil():
    try:
        from PIL import Image
    except ImportError:
        raise GateError("Pillow is not installed (needed to read image metadata)") from None
    return Image


# Pillow info keys that describe how to decode the pixels, not who made them or where.
TECHNICAL = {"dpi", "gamma", "srgb", "chromaticity", "transparency", "interlace", "aspect",
             "icc_profile", "exif", "duration", "loop", "background", "version", "extension",
             "jfif", "jfif_version", "jfif_density", "jfif_unit", "progressive", "progression",
             "adobe", "adobe_transform", "lossless", "compression", "dqt"}


def image_metadata(data, name):
    """(text of every non-technical metadata field, has_gps) for one image's bytes."""
    Image = _pil()
    try:
        im = Image.open(io.BytesIO(data))
    except Exception as e:
        raise GateError(f"{name}: cannot open image: {e}") from None
    parts = []
    for k, v in im.info.items():
        if k in TECHNICAL:
            continue
        parts.append(f"{k}: {v.decode('utf-8', 'replace') if isinstance(v, bytes) else v}")
    try:
        exif = im.getexif()
        for tag, v in exif.items():
            parts.append(f"exif {tag}: {v.decode('utf-8', 'replace') if isinstance(v, bytes) else v}")
        gps = GPS_IFD in exif or bool(exif.get_ifd(GPS_IFD))
        # The Exif sub-IFD holds camera owner, serial numbers and user comments.
        for tag, v in (exif.get_ifd(0x8769).items() if 0x8769 in exif else ()):
            parts.append(f"exif {tag}: {v.decode('utf-8', 'replace') if isinstance(v, bytes) else v}")
    except Exception as e:
        raise GateError(f"{name}: cannot read image metadata: {e}") from None
    return "\n".join(parts), gps


def has_metadata(data, name):
    text, gps = image_metadata(data, name)
    return bool(text) or gps


def font_strings(data):
    """The readable strings of a font (its name table: copyright, designer, licence...), stored
    as ASCII or as UTF-16BE."""
    ascii_runs = re.findall(rb"[\x20-\x7e]{4,}", data)
    utf16_runs = re.findall(rb"(?:\x00[\x20-\x7e]){4,}", data)
    return "\n".join([r.decode() for r in ascii_runs] + [r.decode("utf-16-be") for r in utf16_runs])


def _run(cmd, name):
    if shutil.which(cmd[0]) is None:
        raise GateError(f"{cmd[0]} is not installed (needed to read {name})")
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise GateError(f"{name}: {cmd[0]} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout.decode("utf-8", "replace")


def texts(path):
    """Yield (label, text) for everything readable in one file. Also yields ("GPS", label) for an
    image that carries a GPS position, so callers can refuse it."""
    path = Path(path)
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        yield f"{path} (text)", _run(["pdftotext", "-q", str(path), "-"], path)
        yield f"{path} (metadata)", _run(["pdfinfo", str(path)], path)
        yield f"{path} (XMP metadata)", _run(["pdfinfo", "-meta", str(path)], path)
        attached = _run(["pdfdetach", "-list", str(path)], path)
        if not attached.strip().startswith("0 embedded files"):
            raise GateError(f"{path}: PDF with embedded files, which the gate cannot read: {attached.strip()}")
    elif suffix == ".epub" or (suffix == ".zip"):
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise GateError(f"{path}: not a readable archive: {e}") from None
        for info in z.infolist():
            member = z.read(info)
            label = f"{path}!{info.filename}"
            yield f"{label} (member name)", info.filename
            if Path(info.filename).suffix.lower() in IMAGE_EXT:
                text, gps = image_metadata(member, label)
                if text:
                    yield f"{label} (metadata)", text
                if gps:
                    yield "GPS", label
            elif not _is_binary(member):
                yield label, member.decode("utf-8", "replace")
            elif info.filename.lower().endswith((".ttf", ".otf")):
                yield f"{label} (font strings)", font_strings(member)
            else:
                raise GateError(f"{label}: binary member the gate cannot read")
    elif suffix in IMAGE_EXT:
        text, gps = image_metadata(data, path)
        if text:
            yield f"{path} (metadata)", text
        if gps:
            yield "GPS", str(path)
    elif not _is_binary(data):
        yield str(path), data.decode("utf-8", "replace")
    else:
        raise GateError(f"{path}: binary file of a kind the gate cannot read ({suffix or 'no extension'})")
