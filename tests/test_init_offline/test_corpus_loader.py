import io
import zipfile

from init_offline.corpus_loader import iter_corpus_lines
from init_offline.models import SentenceRef


def make_zip_bytes(files):
    """files: dict[str, str] mapping archive path -> file content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def write_temp_zip(tmp_path, files):
    zip_path = tmp_path / "corpus.zip"
    zip_path.write_bytes(make_zip_bytes(files))
    return str(zip_path)


def test_reads_lines_with_zero_based_offsets(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"file.txt": "first line\nsecond line\nthird line\n"})

    refs = list(iter_corpus_lines(zip_path))

    assert refs == [
        SentenceRef("first line", "file.txt", 0),
        SentenceRef("second line", "file.txt", 1),
        SentenceRef("third line", "file.txt", 2),
    ]


def test_skips_empty_lines(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"file.txt": "line one\n\n   \nline two\n"})

    refs = list(iter_corpus_lines(zip_path))

    assert [r.original_text for r in refs] == ["line one", "line two"]
    # offsets are preserved from the ORIGINAL file, including skipped blank lines.
    assert [r.offset for r in refs] == [0, 3]


def test_walks_nested_folders(tmp_path):
    zip_path = write_temp_zip(
        tmp_path,
        {
            "top.txt": "top level\n",
            "sub/nested.txt": "one level deep\n",
            "sub/deeper/nested2.txt": "two levels deep\n",
        },
    )

    refs = list(iter_corpus_lines(zip_path))
    source_paths = {r.source_path for r in refs}

    assert source_paths == {"top.txt", "sub/nested.txt", "sub/deeper/nested2.txt"}


def test_ignores_non_txt_files(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"notes.txt": "keep me\n", "image.png": "binary junk"})

    refs = list(iter_corpus_lines(zip_path))

    assert len(refs) == 1
    assert refs[0].source_path == "notes.txt"


def test_falls_back_to_latin1_on_invalid_utf8(tmp_path):
    zip_path = tmp_path / "corpus.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        # 0xFF is invalid as a UTF-8 continuation byte but valid in latin-1.
        zf.writestr("weird.txt", b"caf\xe9 line\n")

    refs = list(iter_corpus_lines(str(zip_path)))

    assert len(refs) == 1
    assert refs[0].original_text == "caf\xe9 line"
