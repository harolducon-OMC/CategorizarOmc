"""Comandos de administración que SOLO se ejecutan con acceso al servidor o a la base de datos.

Uso (desde la carpeta backend, con DATABASE_URL apuntando a la base correcta):

    python -m app.cli promote-superadmin correo@empresa.com

La cuenta debe existir (la persona se registra primero con normalidad). Hecho así, nadie puede convertirse en
super administrador desde internet, ni siquiera registrándose con el correo del jefe antes que él.
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from . import accounts  # noqa: E402  (después de cargar el .env)
from .db import SessionLocal  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Administración de la plataforma de Insights.")
    commands = parser.add_subparsers(dest="command", required=True)
    promote = commands.add_parser("promote-superadmin", help="Convierte una cuenta existente en super administrador (solo si aún no hay uno).")
    promote.add_argument("email", help="Correo de la cuenta que será super administrador.")
    args = parser.parse_args(argv)

    if args.command == "promote-superadmin":
        with SessionLocal() as db:
            try:
                email = accounts.promote_super_admin(db, args.email)
            except accounts.SuperAdminError as exc:
                print(f"No se pudo asignar: {exc}", file=sys.stderr)
                return 1
        print(f"Listo: {email} ahora es super administrador. Debe iniciar sesión de nuevo.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
