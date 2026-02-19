from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "HIVE Food Coordinator")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hive_food.db")

# Comma-separated list of email domains permitted to register
ALLOWED_EMAIL_DOMAINS = [d.strip().lower() for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",") if d.strip()]

ADMIN_BOOTSTRAP_EMAIL = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin@hive-gp.de").lower()
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "ChangeMe123!")
