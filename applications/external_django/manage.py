#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conduit.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:

        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. am i you sure it's installed and "
                "available on my PYTHONPATH environment variable? Did i "
                "forget to activate a virtual environment?"
            )
        raise
    execute_from_command_line(sys.argv)
