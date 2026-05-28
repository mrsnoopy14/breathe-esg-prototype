"""
Management command: create_demo_data

Creates the minimum seed data needed to run and demo the platform:

  Company:   Acme Manufacturing  (slug: acme)
  Admin:     admin / demo1234    (role: ADMIN,   superuser)
  Analyst:   analyst / demo1234  (role: ANALYST)

Run with:
    python manage.py create_demo_data

The command is idempotent — it checks whether the admin user already exists
before creating anything, so it is safe to call from build.sh on re-deploys.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import Company

User = get_user_model()

COMPANY_NAME = 'Acme Manufacturing'
COMPANY_SLUG = 'acme'
DEMO_PASSWORD = 'demo1234'


class Command(BaseCommand):
    help = 'Create demo company, admin, and analyst users for the ESG platform.'

    def handle(self, *args, **options):
        # --- Guard: skip if admin already exists ---
        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING(
                "Demo data already exists (user 'admin' found). Skipping."
            ))
            return

        # --- Company ---
        company, company_created = Company.objects.get_or_create(
            slug=COMPANY_SLUG,
            defaults={'name': COMPANY_NAME},
        )
        if company_created:
            self.stdout.write(f"  Created company: {company.name}  (id={company.pk})")
        else:
            self.stdout.write(f"  Company already exists: {company.name}  (id={company.pk})")

        # --- Admin / superuser ---
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@acme.example.com',
            password=DEMO_PASSWORD,
        )
        admin_user.company = company
        admin_user.role = User.ROLE_ADMIN
        admin_user.save()
        self.stdout.write(f"  Created superuser:  admin / {DEMO_PASSWORD}  (id={admin_user.pk})")

        # --- Analyst user ---
        analyst_user = User.objects.create_user(
            username='analyst',
            email='analyst@acme.example.com',
            password=DEMO_PASSWORD,
        )
        analyst_user.company = company
        analyst_user.role = User.ROLE_ANALYST
        analyst_user.save()
        self.stdout.write(f"  Created analyst:    analyst / {DEMO_PASSWORD}  (id={analyst_user.pk})")

        self.stdout.write(self.style.SUCCESS(
            "\nDemo data created successfully.\n"
            "  Admin login:   admin / demo1234\n"
            "  Analyst login: analyst / demo1234\n"
        ))
