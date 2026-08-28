"""Local recovery command for a demo installation.

Run only when the system administrator must be intentionally reset.
"""

from sqlalchemy import delete

from .auth import ensure_bootstrap_system_admin
from .database import Base, SessionLocal, engine
from .models import User, UserRole


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.execute(delete(User).where(User.role == UserRole.system_admin))
        db.commit()
        ensure_bootstrap_system_admin(db)
    print("System administrator reset completed.")


if __name__ == "__main__":
    main()
