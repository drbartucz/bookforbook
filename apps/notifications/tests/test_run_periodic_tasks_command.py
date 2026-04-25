from unittest.mock import patch

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestRunPeriodicTasksCommand:
    def test_runs_only_selected_task(self):
        with patch("apps.matching.tasks.run_periodic_matching") as mock_matching, patch(
            "apps.matching.tasks.expire_old_matches"
        ) as mock_expire, patch(
            "apps.notifications.tasks.check_inactivity"
        ) as mock_inactivity, patch(
            "apps.notifications.tasks.finalize_scheduled_account_deletions"
        ) as mock_deletions, patch(
            "apps.trading.tasks.send_rating_reminders"
        ) as mock_rating, patch(
            "apps.trading.tasks.auto_close_trades"
        ) as mock_auto_close:
            call_command("run_periodic_tasks", task="matching")

        mock_matching.assert_called_once_with()
        mock_expire.assert_not_called()
        mock_inactivity.assert_not_called()
        mock_deletions.assert_not_called()
        mock_rating.assert_not_called()
        mock_auto_close.assert_not_called()

    def test_runs_all_tasks_when_task_all(self):
        with patch("apps.matching.tasks.run_periodic_matching") as mock_matching, patch(
            "apps.matching.tasks.expire_old_matches"
        ) as mock_expire, patch(
            "apps.notifications.tasks.check_inactivity"
        ) as mock_inactivity, patch(
            "apps.notifications.tasks.finalize_scheduled_account_deletions"
        ) as mock_deletions, patch(
            "apps.trading.tasks.send_rating_reminders"
        ) as mock_rating, patch(
            "apps.trading.tasks.auto_close_trades"
        ) as mock_auto_close:
            call_command("run_periodic_tasks", task="all")

        mock_matching.assert_called_once_with()
        mock_expire.assert_called_once_with()
        mock_inactivity.assert_called_once_with()
        mock_deletions.assert_called_once_with()
        mock_rating.assert_called_once_with()
        mock_auto_close.assert_called_once_with()
