from pydantic import BaseModel, ConfigDict


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None


ROLE_CUSTOMER = "CUSTOMER"
ROLE_ADMIN = "ADMIN"
ROLE_SUPER_ADMIN = "SUPER_ADMIN"

DEFAULT_ROLES: list[tuple[str, str]] = [
    (ROLE_CUSTOMER, "Cliente de la tienda"),
    (ROLE_ADMIN, "Administrador de la plataforma"),
    (ROLE_SUPER_ADMIN, "Super administrador con acceso total"),
]
