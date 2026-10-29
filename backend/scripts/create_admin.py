"""Yonetici hesabi olusturur ya da kayitli bir kullaniciyi yonetici yapar.

Kullanim (api container'i icinde):

    python -m scripts.create_admin --email yonetici@example.com

Kullanici yoksa parola etkilesimli sorulur (ya da ADMIN_PASSWORD ortam
degiskeninden okunur) ve e-postasi dogrulanmis bir yonetici olusturulur.
Kullanici varsa parolasina dokunulmaz; yalniz rolu `admin`, durumu `ACTIVE`
yapilir ve e-postasi dogrulanmis sayilir.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.auth.security import hash_password, normalize_email, password_problem
from app.auth.service import utcnow
from app.core.db import session_factory
from app.models import AppUser


def _read_password() -> str | None:
    password = os.environ.get("ADMIN_PASSWORD")
    if password:
        return password
    first = getpass.getpass("Parola: ")
    if first != getpass.getpass("Parola (tekrar): "):
        print("Parolalar eşleşmiyor.", file=sys.stderr)
        return None
    return first


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Yönetici")
    args = parser.parse_args(argv)

    email = normalize_email(args.email)
    if email is None:
        print("Geçerli bir e-posta adresi gir.", file=sys.stderr)
        return 1
    async with session_factory() as session:
        user = await session.scalar(select(AppUser).where(AppUser.email == email))
        now = utcnow()
        if user is not None:
            user.role = "admin"
            user.status = "ACTIVE"
            user.email_verified_at = user.email_verified_at or now
            await session.commit()
            print(f"{email} yönetici yapıldı.")
            return 0

        password = _read_password()
        if password is None:
            return 1
        problem = password_problem(password)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        session.add(
            AppUser(
                email=email,
                password_hash=await hash_password(password),
                display_name=args.name[:64],
                role="admin",
                status="ACTIVE",
                email_verified_at=now,
            )
        )
        await session.commit()
    print(f"{email} yönetici hesabı oluşturuldu. /giris sayfasından girebilirsin.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
