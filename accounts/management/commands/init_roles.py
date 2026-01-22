from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create user roles and assign base permissions"

    def handle(self, *_args: str, **_options: object) -> None:
        # Define roles and required permission codenames
        roles = {
            "seeker": [
                "add_application",
                "change_application",
                "view_application",
            ],
            "poster": [
                "add_job",
                "change_job",
                "view_job",
            ],
            "admin": [
                "moderate_job",
                "verify_profile",
                "view_user",
                "change_user",
            ],
        }

        for role_name, perm_codenames in roles.items():
            role_group, _created = Group.objects.get_or_create(name=role_name)
            for codename in perm_codenames:
                # Attempt to find permission by codename across all registered apps
                try:
                    perm = Permission.objects.get(codename=codename)
                    role_group.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"Permission not found for codename: {codename}")
                    )

            self.stdout.write(self.style.SUCCESS(f"Role ready: {role_name} ({role_group.pk})"))
