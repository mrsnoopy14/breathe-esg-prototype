from django.contrib.auth.models import AbstractUser
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_ANALYST = 'ANALYST'
    ROLE_ADMIN = 'ADMIN'
    ROLE_CHOICES = [(ROLE_ANALYST, 'Analyst'), (ROLE_ADMIN, 'Admin')]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)

    def __str__(self):
        return f"{self.username} ({self.company})"
