"""Integration tests for CheckRunPublisher against a mocked GitHub API.

Tests the full HTTP path: CheckRunPublisher → HttpCheckRunClient → httpx transport.
The mock transport intercepts HTTP calls at the network boundary, verifying that
correct GitHub Check Runs API requests are formed and payloads are well-formed.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest

from kenjutsu.models.findings import (
    Category,
    Confidence,
    Finding,
    Origin,
    Publishability,
    Severity,
)
from kenjutsu.publisher.check_run import CheckRunPublisher

# ---------------------------------------------------------------------------
# Concrete HTTP client (implements CheckRunClient protocol over httpx)
# ---------------------------------------------------------------------------

_GITHUB_API_BASE = "https://api.github.com"


class HttpCheckRunClient:
    """Minimal GitHub Check Runs client backed by httpx.AsyncClient."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def create_check_run(self, owner: str, repo: str, payload: dict) -> dict:
        resp = await self._client.post(
            f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/check-runs",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def update_check_run(self, owner: str, repo: str, check_run_id: int, payload: dict) -> dict:
        resp = await self._client.patch(
            f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/check-runs/{check_run_id}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Capturing mock transport
# ---------------------------------------------------------------------------


class _CapturingTransport(httpx.AsyncBaseTransport):
    """Records all async requests, returns canned GitHub-like responses."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            return httpx.Response(201, json={"id": _CHECK_RUN_ID})
        return httpx.Response(200, json={"id": _CHECK_RUN_ID})


# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

_OWNER = "acme"
_REPO = "myrepo"
_HEAD_SHA = "abc123def456"
_CHECK_RUN_ID = 99

# GitHub Check Runs API requires YYYY-MM-DDTHH:MM:SSZ (UTC, Z suffix, no microseconds)
_ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _make_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "file_path": "src/auth.py",
        "line_start": 10,
        "line_end": 12,
        "origin": Origin.LLM,
        "confidence": Confidence.HIGH,
        "severity": Severity.WARNING,
        "category": Category.BUG,
        "publishability": Publishability.PUBLISH,
        "description": "Potential null dereference",
    }
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckRunPublisherIntegration:
    async def test_create_posts_to_correct_endpoint(self) -> None:
        """create() POSTs to /repos/{owner}/{repo}/check-runs with required fields."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            run_id = await publisher.create()

        assert run_id == _CHECK_RUN_ID
        assert len(transport.requests) == 1
        req = transport.requests[0]
        assert req.method == "POST"
        assert f"/repos/{_OWNER}/{_REPO}/check-runs" in str(req.url)

        body = json.loads(req.content)
        assert body["head_sha"] == _HEAD_SHA
        assert body["status"] == "in_progress"
        assert _ISO_Z_RE.match(body["started_at"]), (
            f"started_at must be YYYY-MM-DDTHH:MM:SSZ, got: {body['started_at']!r}"
        )

    async def test_update_with_annotations_patches_correct_endpoint(self) -> None:
        """update_with_annotations() PATCHes /check-runs/{id} with annotation payload."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            await publisher.update_with_annotations(_CHECK_RUN_ID, [_make_finding()])

        assert len(transport.requests) == 1
        req = transport.requests[0]
        assert req.method == "PATCH"
        assert f"/check-runs/{_CHECK_RUN_ID}" in str(req.url)

        body = json.loads(req.content)
        annotations = body["output"]["annotations"]
        assert len(annotations) == 1
        assert annotations[0]["path"] == "src/auth.py"
        assert annotations[0]["annotation_level"] == "warning"
        assert annotations[0]["start_line"] == 10
        assert annotations[0]["end_line"] == 12

    async def test_complete_patches_with_iso_z_timestamp(self) -> None:
        """complete() sets completed_at in YYYY-MM-DDTHH:MM:SSZ format (GitHub requirement)."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            findings = [_make_finding(severity=Severity.CRITICAL)]
            await publisher.complete(_CHECK_RUN_ID, findings, [], duration_seconds=2.5)

        assert len(transport.requests) == 1
        req = transport.requests[0]
        assert req.method == "PATCH"

        body = json.loads(req.content)
        assert body["status"] == "completed"
        assert body["conclusion"] == "failure"
        assert _ISO_Z_RE.match(body["completed_at"]), (
            f"completed_at must be YYYY-MM-DDTHH:MM:SSZ, got: {body['completed_at']!r}"
        )

    async def test_complete_does_not_include_annotations(self) -> None:
        """complete() must not re-send annotations (avoids GitHub duplicates)."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            findings = [_make_finding()]
            await publisher.complete(_CHECK_RUN_ID, findings, [], duration_seconds=1.0)

        body = json.loads(transport.requests[0].content)
        assert "annotations" not in body.get("output", {}), (
            "complete() must not include annotations to avoid GitHub duplicates"
        )

    async def test_full_lifecycle_no_http_errors(self) -> None:
        """Full pipeline: create → update → complete issues exactly 3 HTTP requests."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            run_id = await publisher.create()
            findings = [_make_finding(), _make_finding(severity=Severity.SUGGESTION)]
            await publisher.update_with_annotations(run_id, findings)
            await publisher.complete(run_id, findings, [], duration_seconds=4.0)

        # 1 POST (create) + 1 PATCH (annotations) + 1 PATCH (complete)
        assert len(transport.requests) == 3

    async def test_suppressed_finding_not_sent_as_annotation(self) -> None:
        """SUPPRESS findings must not appear as annotations in the HTTP request."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            findings = [
                _make_finding(publishability=Publishability.SUPPRESS),
                _make_finding(publishability=Publishability.PUBLISH),
            ]
            await publisher.update_with_annotations(_CHECK_RUN_ID, findings)

        # Only 1 publishable finding → exactly 1 PATCH
        assert len(transport.requests) == 1
        body = json.loads(transport.requests[0].content)
        annotations = body["output"]["annotations"]
        assert len(annotations) == 1

    async def test_predictive_finding_not_sent_as_annotation(self) -> None:
        """PREDICTIVE origin findings must produce no annotation PATCH calls."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            findings = [_make_finding(origin=Origin.PREDICTIVE, publishability=Publishability.PUBLISH)]
            await publisher.update_with_annotations(_CHECK_RUN_ID, findings)

        # No publishable annotations → no HTTP call made
        assert len(transport.requests) == 0

    async def test_large_finding_set_batched_across_multiple_requests(self) -> None:
        """60 publishable findings → 2 PATCH calls (batches of 50 + 10)."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            findings = [_make_finding() for _ in range(60)]
            await publisher.update_with_annotations(_CHECK_RUN_ID, findings)

        assert len(transport.requests) == 2
        batch1 = json.loads(transport.requests[0].content)["output"]["annotations"]
        batch2 = json.loads(transport.requests[1].content)["output"]["annotations"]
        assert len(batch1) == 50
        assert len(batch2) == 10

    async def test_mixed_findings_only_publishable_annotated(self) -> None:
        """Mixed publishable, suppressed, and predictive → only publishable annotated."""
        transport = _CapturingTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = CheckRunPublisher(HttpCheckRunClient(client), _OWNER, _REPO, _HEAD_SHA)
            findings = [
                _make_finding(publishability=Publishability.PUBLISH),
                _make_finding(publishability=Publishability.SUPPRESS),
                _make_finding(origin=Origin.PREDICTIVE, publishability=Publishability.PUBLISH),
                _make_finding(publishability=Publishability.REDACT_AND_PUBLISH),
            ]
            await publisher.update_with_annotations(_CHECK_RUN_ID, findings)

        # 2 publishable (PUBLISH + REDACT_AND_PUBLISH), 1 suppressed, 1 predictive
        assert len(transport.requests) == 1
        body = json.loads(transport.requests[0].content)
        assert len(body["output"]["annotations"]) == 2
