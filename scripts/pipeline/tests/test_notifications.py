"""Exercise event retries against actual downstream publication acknowledgements."""

import io
import unittest
import urllib.error
from unittest.mock import Mock, patch

from scripts.pipeline.notifications import (
    AlreadySynchronized,
    NeverPublished,
    PublishedState,
    SynchronizationRequested,
    ensure_synchronized,
    notify_index,
    notify_legacy,
    published_state,
)


class NotificationTests(unittest.TestCase):
    def test_failed_request_remains_pending_until_a_later_retry_succeeds(self):
        request = Mock(side_effect=[RuntimeError("dispatch failed"), None])
        state = PublishedState("a" * 40)
        with self.assertRaisesRegex(RuntimeError, "dispatch failed"):
            ensure_synchronized("b" * 40, state, request)
        self.assertIsInstance(
            ensure_synchronized("b" * 40, state, request), SynchronizationRequested
        )
        self.assertEqual(request.call_count, 2)
        result = ensure_synchronized("b" * 40, PublishedState("b" * 40), request)
        self.assertIsInstance(result, AlreadySynchronized)
        self.assertEqual(request.call_count, 2)

    def test_missing_marker_is_an_explicit_first_publication(self):
        request = Mock()
        self.assertIsInstance(
            ensure_synchronized("a" * 40, NeverPublished(), request),
            SynchronizationRequested,
        )
        request.assert_called_once()

    def test_only_http_404_means_the_marker_has_not_been_published(self):
        error = urllib.error.HTTPError(
            "https://example/marker", 404, "missing", {}, io.BytesIO()
        )
        self.addCleanup(error.close)
        with patch("urllib.request.urlopen", side_effect=error):
            self.assertIsInstance(
                published_state("https://example/marker"), NeverPublished
            )
        error = urllib.error.HTTPError(
            "https://example/marker", 503, "unavailable", {}, io.BytesIO()
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError):
                published_state("https://example/marker")

    def test_index_retries_even_when_wheels_were_committed_by_an_earlier_attempt(self):
        with (
            patch(
                "scripts.pipeline.notifications.github",
                return_value={"commit": {"tree": {"sha": "b" * 40}}},
            ),
            patch(
                "scripts.pipeline.notifications.published_state",
                return_value=PublishedState("a" * 40),
            ),
            patch("scripts.pipeline.notifications.subprocess.run") as dispatch,
        ):
            notify_index("ririv/py-extra-wheels")
            dispatch.assert_called_once()

    def test_legacy_retries_after_index_deployment_even_without_a_new_index_tree(self):
        with (
            patch(
                "scripts.pipeline.notifications.github",
                return_value={"commit": {"tree": {"sha": "b" * 40}}},
            ),
            patch(
                "scripts.pipeline.notifications.published_state",
                return_value=PublishedState("a" * 40),
            ),
            patch("scripts.pipeline.notifications.subprocess.run") as dispatch,
            patch.dict("os.environ", {"LEGACY_INDEX_DISPATCH_TOKEN": "test-token"}),
        ):
            notify_legacy("ririv/py-extra-wheels")
            dispatch.assert_called_once()

    def test_synced_legacy_does_not_require_a_dispatch(self):
        with (
            patch(
                "scripts.pipeline.notifications.github",
                return_value={"commit": {"tree": {"sha": "a" * 40}}},
            ),
            patch(
                "scripts.pipeline.notifications.published_state",
                return_value=PublishedState("a" * 40),
            ),
            patch("scripts.pipeline.notifications.subprocess.run") as dispatch,
        ):
            notify_legacy("ririv/py-extra-wheels")
            dispatch.assert_not_called()
