from config import read_labels


def test_labels_keep_spaces_accents_and_skip_blank_lines(tmp_path):
    f = tmp_path / "labels.txt"
    f.write_text("espada de são jorge\n\nsamambaia\n", encoding="utf-8")
    assert read_labels(f) == ["espada de são jorge", "samambaia"]
