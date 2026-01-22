from django.contrib.auth.base_user import AbstractBaseUser


def user_has_role(user: AbstractBaseUser, role_name: str) -> bool:
    groups = getattr(user, "groups", None)
    if groups is None:
        return False
    return groups.filter(name=role_name).exists()
