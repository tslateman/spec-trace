#!/usr/bin/env python
"""Setup script to create admin user and perform initial configuration."""

import os
import sys

import django

# Add spectrace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spectrace"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()


def create_admin_user():
    """Create admin user if it doesn't exist."""
    username = "admin"
    email = "admin@localhost"
    password = "admin"

    if User.objects.filter(username=username).exists():
        print(f"Admin user '{username}' already exists")
        return

    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Created admin user '{username}' with password '{password}'")


if __name__ == "__main__":
    create_admin_user()
