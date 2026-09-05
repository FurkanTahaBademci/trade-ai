"""SQLAlchemy modelleri.

Faz 1'den itibaren buraya modeller eklenecek (instrument, price_daily, ...).
Her yeni model dosyasi burada import edilmeli ki Alembic autogenerate
onu görsün (bkz. alembic/env.py -> target_metadata).
"""

from app.core.db import Base

__all__ = ["Base"]
