"""trade-ai backend paketi."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Tek kaynak kok dizindeki VERSION dosyasidir; ops/release.sh onu
    # pyproject.toml'a yazar, paket metadatasi da oradan gelir.
    __version__ = version("trade-ai-backend")
except PackageNotFoundError:  # paket kurulmadan (or. dogrudan PYTHONPATH ile) calisirken
    __version__ = "0.0.0+unknown"
