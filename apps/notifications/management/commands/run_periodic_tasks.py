"""
Management command to run all periodic background tasks.
Intended to be called from cron — replaces qcluster for shared hosting
environments that lack /dev/shm (e.g. SureSupport).

Crontab example:
    # Every 6 hours — matching scan
    0 */6 * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=matching

    # Every hour — expire old matches
    0 * * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=expire_matches

    # Daily — inactivity check
    0 2 * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=inactivity
    # Daily — inventory ownership reconcile
    30 2 * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=inventory_ownership

    # Weekly — rating reminders + auto-close trades (Sunday 3am)
    0 3 * * 0 /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=rating_reminders
    0 3 * * 0 /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=auto_close

    # Or run all at once (less granular):
    0 3 * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=all
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

TASKS = {
    "matching": "apps.matching.tasks.run_periodic_matching",
    "expire_matches": "apps.matching.tasks.expire_old_matches",
    "inactivity": "apps.notifications.tasks.check_inactivity",
    "inventory_ownership": "apps.notifications.tasks.reconcile_inventory_user_ownership",
    "account_deletions": "apps.notifications.tasks.finalize_scheduled_account_deletions",
    "rating_reminders": "apps.trading.tasks.send_rating_reminders",
    "auto_close": "apps.trading.tasks.auto_close_trades",
}


class Command(BaseCommand):
    help = "Run periodic background tasks (for use with cron instead of qcluster)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--task",
            choices=list(TASKS.keys()) + ["all"],
            default="all",
            help="Which task to run (default: all)",
        )

    def handle(self, *args, **options):
        task_arg = options["task"]
        to_run = TASKS.items() if task_arg == "all" else [(task_arg, TASKS[task_arg])]

        for name, func_path in to_run:
            self.stdout.write(f"Running {name}...")
            try:
                module_path, func_name = func_path.rsplit(".", 1)
                import importlib

                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                func()
                self.stdout.write(self.style.SUCCESS(f"  {name} completed"))
            except Exception:
                logger.exception("Periodic task %s failed", name)
                self.stdout.write(self.style.ERROR(f"  {name} failed (see logs)"))
