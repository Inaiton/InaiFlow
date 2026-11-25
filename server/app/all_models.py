"""Import every module's models so ``Base.metadata`` is complete (Alembic env, tests, CLI)."""

from app.core.db import Base
from app.modules.accounts import models as accounts_models
from app.modules.documents import models as documents_models
from app.modules.identity import models as identity_models
from app.modules.operations import models as operations_models
from app.modules.organization import models as organization_models
from app.modules.payroll import models as payroll_models
from app.modules.platform import models as platform_models
from app.modules.rbac import models as rbac_models
from app.modules.superadmin import models as superadmin_models
from app.modules.taxation import models as taxation_models

metadata = Base.metadata

__all__ = [
    "Base",
    "accounts_models",
    "documents_models",
    "identity_models",
    "metadata",
    "operations_models",
    "organization_models",
    "payroll_models",
    "platform_models",
    "rbac_models",
    "superadmin_models",
    "taxation_models",
]
