import pickle
import sys

from src.init_offline import CorpusIndex
from src.init_offline import corpus_index as corpus_index_module


def test_load_index_retries_cache_created_with_legacy_package_name(tmp_path, monkeypatch):
    path = tmp_path / "legacy.pickle"
    path.write_bytes(pickle.dumps(CorpusIndex()))
    real_load = pickle.load
    calls = 0

    def fail_once(file_object):
        nonlocal calls
        calls += 1
        if calls == 1:
            error = ModuleNotFoundError("No module named 'init_offline'")
            error.name = "init_offline"
            raise error
        return real_load(file_object)

    monkeypatch.delitem(sys.modules, "init_offline", raising=False)
    monkeypatch.setattr(corpus_index_module.pickle, "load", fail_once)

    loaded = corpus_index_module.load_index(str(path))

    assert isinstance(loaded, CorpusIndex)
    assert calls == 2
