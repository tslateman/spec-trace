"""GitHub App authentication and API client for CI/CD integration."""

import hashlib
import hmac
import io
import logging
import time
import zipfile
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"

# JWT expiration (10 minutes max per GitHub docs)
JWT_EXPIRATION_SECONDS = 600

# Installation token cache duration (tokens last 1 hour, cache for 50 minutes)
INSTALLATION_TOKEN_CACHE_SECONDS = 3000

# Retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 30.0  # seconds
DEFAULT_BACKOFF_MULTIPLIER = 2.0

# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    retryable_exceptions: tuple = (requests.RequestException,),
):
    """Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries.
        backoff_multiplier: Multiplier for delay after each retry.
        retryable_exceptions: Tuple of exceptions to retry on.

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    # Check if it's an HTTP error with retryable status
                    if isinstance(e, requests.HTTPError) and e.response is not None:
                        if e.response.status_code not in RETRYABLE_STATUS_CODES:
                            # Not a retryable status code, raise immediately
                            raise

                    if attempt == max_retries:
                        # Last attempt, raise the exception
                        raise

                    # Log and wait before retry
                    logger.warning(
                        "Retry %d/%d for %s after error: %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        e,
                    )
                    time.sleep(delay)
                    delay = min(delay * backoff_multiplier, max_delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


@dataclass
class GitHubArtifact:
    """Represents a GitHub Actions artifact."""

    id: int
    name: str
    size_in_bytes: int
    archive_download_url: str
    expired: bool


@dataclass
class GitHubWorkflowRun:
    """Represents a GitHub Actions workflow run from webhook payload."""

    id: int
    name: str
    head_branch: str
    head_sha: str
    conclusion: str  # success, failure, cancelled, etc.
    html_url: str
    repository_full_name: str
    artifacts_url: str


class GitHubAppError(Exception):
    """Base exception for GitHub App errors."""

    pass


class GitHubAuthError(GitHubAppError):
    """Authentication or authorization error."""

    pass


class GitHubArtifactError(GitHubAppError):
    """Error fetching or processing artifacts."""

    pass


class GitHubClient:
    """Client for GitHub App API operations.

    Handles JWT generation, installation token fetching, and artifact downloads.
    """

    def __init__(
        self,
        app_id: str | None = None,
        private_key: str | None = None,
    ):
        """Initialize GitHub client.

        Args:
            app_id: GitHub App ID. Defaults to settings.GITHUB_APP_ID.
            private_key: GitHub App private key (PEM format).
                Defaults to settings.GITHUB_PRIVATE_KEY.
        """
        self.app_id = app_id or getattr(settings, "GITHUB_APP_ID", "")
        self.private_key = private_key or getattr(settings, "GITHUB_PRIVATE_KEY", "")
        self._installation_tokens: dict[int, tuple[str, float]] = {}

    def _generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        Returns:
            JWT token string.

        Raises:
            GitHubAuthError: If app_id or private_key is not configured.
            ImportError: If PyJWT is not installed.
        """
        try:
            import jwt
        except ImportError:
            raise ImportError(
                "GitHub integration requires extra dependencies. "
                "Install with: pip install spectrace[github]"
            )

        if not self.app_id or not self.private_key:
            raise GitHubAuthError(
                "GitHub App credentials not configured. Set GITHUB_APP_ID and GITHUB_PRIVATE_KEY."
            )

        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago (clock skew tolerance)
            "exp": now + JWT_EXPIRATION_SECONDS,
            "iss": self.app_id,
        }

        # Handle private key that may have escaped newlines
        private_key = self.private_key.replace("\\n", "\n")

        try:
            token = jwt.encode(payload, private_key, algorithm="RS256")
            return token
        except Exception as e:
            raise GitHubAuthError(f"Failed to generate JWT: {e}") from e

    def get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token for API calls.

        Tokens are cached for 50 minutes (they last 1 hour).

        Args:
            installation_id: The GitHub App installation ID.

        Returns:
            Installation access token.

        Raises:
            GitHubAuthError: If token generation fails.
        """
        # Check cache
        cached = self._installation_tokens.get(installation_id)
        if cached:
            token, expires_at = cached
            if time.time() < expires_at:
                return token

        # Generate new token
        jwt_token = self._generate_jwt()

        url = f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            token = self._fetch_installation_token(url, headers)
        except requests.RequestException as e:
            raise GitHubAuthError(f"Failed to get installation token: {e}") from e

        # Cache token (expires in ~50 minutes)
        expires_at = time.time() + INSTALLATION_TOKEN_CACHE_SECONDS
        self._installation_tokens[installation_id] = (token, expires_at)

        return token

    @retry_with_backoff()
    def _fetch_installation_token(self, url: str, headers: dict) -> str:
        """Fetch installation token with retry logic."""
        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()["token"]

    def list_artifacts(
        self,
        owner: str,
        repo: str,
        run_id: int,
        installation_id: int,
    ) -> list[GitHubArtifact]:
        """List artifacts for a workflow run.

        Args:
            owner: Repository owner.
            repo: Repository name.
            run_id: Workflow run ID.
            installation_id: GitHub App installation ID.

        Returns:
            List of artifacts.

        Raises:
            GitHubArtifactError: If listing fails.
        """
        token = self.get_installation_token(installation_id)

        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        artifacts = []
        page = 1

        while True:
            try:
                data = self._fetch_artifacts_page(url, headers, page)
            except requests.RequestException as e:
                raise GitHubArtifactError(f"Failed to list artifacts: {e}") from e

            for artifact in data.get("artifacts", []):
                artifacts.append(
                    GitHubArtifact(
                        id=artifact["id"],
                        name=artifact["name"],
                        size_in_bytes=artifact["size_in_bytes"],
                        archive_download_url=artifact["archive_download_url"],
                        expired=artifact["expired"],
                    )
                )

            # Check for more pages
            if len(data.get("artifacts", [])) < 100:
                break
            page += 1

        return artifacts

    @retry_with_backoff()
    def _fetch_artifacts_page(self, url: str, headers: dict, page: int) -> dict:
        """Fetch a page of artifacts with retry logic."""
        response = requests.get(
            url,
            headers=headers,
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def download_artifact(
        self,
        owner: str,
        repo: str,
        artifact_id: int,
        installation_id: int,
        max_size_bytes: int = 100 * 1024 * 1024,  # 100MB default
    ) -> bytes:
        """Download an artifact ZIP file.

        Args:
            owner: Repository owner.
            repo: Repository name.
            artifact_id: Artifact ID.
            installation_id: GitHub App installation ID.
            max_size_bytes: Maximum allowed artifact size.

        Returns:
            Artifact content as bytes.

        Raises:
            GitHubArtifactError: If download fails or artifact too large.
        """
        token = self.get_installation_token(installation_id)

        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            return self._download_artifact_with_retry(url, headers, max_size_bytes)
        except requests.RequestException as e:
            raise GitHubArtifactError(f"Failed to download artifact: {e}") from e

    @retry_with_backoff()
    def _download_artifact_with_retry(
        self,
        url: str,
        headers: dict,
        max_size_bytes: int,
    ) -> bytes:
        """Download artifact with retry logic."""
        response = requests.get(
            url,
            headers=headers,
            timeout=60,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Check content length
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_size_bytes:
            raise GitHubArtifactError(
                f"Artifact too large: {content_length} bytes (max {max_size_bytes})"
            )

        # Stream download with size limit
        chunks = []
        total_size = 0
        for chunk in response.iter_content(chunk_size=8192):
            total_size += len(chunk)
            if total_size > max_size_bytes:
                raise GitHubArtifactError(
                    f"Artifact exceeded size limit during download: {total_size} bytes"
                )
            chunks.append(chunk)

        return b"".join(chunks)

    def extract_files_from_artifact(
        self,
        artifact_content: bytes,
        filenames: list[str],
    ) -> dict[str, bytes]:
        """Extract specific files from an artifact ZIP.

        Args:
            artifact_content: ZIP file content as bytes.
            filenames: List of filenames to extract.

        Returns:
            Dict mapping filename to content for files that exist.
        """
        result = {}

        try:
            with zipfile.ZipFile(io.BytesIO(artifact_content)) as zf:
                for filename in filenames:
                    try:
                        content = zf.read(filename)
                        result[filename] = content
                    except KeyError:
                        # File not in ZIP, skip
                        logger.debug(f"File {filename} not found in artifact")
        except zipfile.BadZipFile as e:
            raise GitHubArtifactError(f"Invalid ZIP file: {e}") from e

        return result

    def fetch_test_artifacts(
        self,
        owner: str,
        repo: str,
        run_id: int,
        installation_id: int,
        artifact_name: str = "test-results",
        required_files: list[str] | None = None,
    ) -> dict[str, bytes]:
        """Fetch and extract test result files from a workflow run artifact.

        This is a convenience method that:
        1. Lists artifacts for the run
        2. Finds the artifact by name
        3. Downloads and extracts the required files

        Args:
            owner: Repository owner.
            repo: Repository name.
            run_id: Workflow run ID.
            installation_id: GitHub App installation ID.
            artifact_name: Name of the artifact to download (default: "test-results").
            required_files: Files to extract. Defaults to ["junit.xml", "links.json"].

        Returns:
            Dict mapping filename to content for files that exist.

        Raises:
            GitHubArtifactError: If artifact not found or download fails.
        """
        if required_files is None:
            required_files = ["junit.xml", "links.json"]

        # List artifacts
        artifacts = self.list_artifacts(owner, repo, run_id, installation_id)

        # Find the target artifact
        target_artifact = None
        for artifact in artifacts:
            if artifact.name == artifact_name and not artifact.expired:
                target_artifact = artifact
                break

        if not target_artifact:
            available_names = [a.name for a in artifacts if not a.expired]
            raise GitHubArtifactError(
                f"Artifact '{artifact_name}' not found. Available: {available_names}"
            )

        logger.info(
            "Downloading artifact '%s' (%d bytes) from %s/%s run %d",
            artifact_name,
            target_artifact.size_in_bytes,
            owner,
            repo,
            run_id,
        )

        # Download and extract
        content = self.download_artifact(owner, repo, target_artifact.id, installation_id)
        files = self.extract_files_from_artifact(content, required_files)

        logger.info(
            "Extracted %d files from artifact: %s",
            len(files),
            list(files.keys()),
        )

        return files


def verify_webhook_signature(
    payload: bytes,
    signature_header: str,
    secret: str | None = None,
) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    Args:
        payload: Raw request body.
        signature_header: Value of X-Hub-Signature-256 header.
        secret: Webhook secret. Defaults to settings.GITHUB_WEBHOOK_SECRET.

    Returns:
        True if signature is valid.
    """
    secret = secret or getattr(settings, "GITHUB_WEBHOOK_SECRET", "")

    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not configured, skipping verification")
        return True  # Allow in dev mode

    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature format (expected sha256=...)")
        return False

    expected_signature = signature_header[7:]  # Remove "sha256=" prefix

    computed = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected_signature)


def parse_workflow_run_event(payload: dict[str, Any]) -> GitHubWorkflowRun | None:
    """Parse a workflow_run webhook payload.

    Args:
        payload: Parsed JSON payload from webhook.

    Returns:
        GitHubWorkflowRun if valid workflow_run.completed event, None otherwise.
    """
    action = payload.get("action")
    if action != "completed":
        logger.debug(f"Ignoring workflow_run action: {action}")
        return None

    workflow_run = payload.get("workflow_run", {})
    repository = payload.get("repository", {})

    if not workflow_run or not repository:
        logger.warning("Missing workflow_run or repository in payload")
        return None

    return GitHubWorkflowRun(
        id=workflow_run.get("id"),
        name=workflow_run.get("name", ""),
        head_branch=workflow_run.get("head_branch", ""),
        head_sha=workflow_run.get("head_sha", ""),
        conclusion=workflow_run.get("conclusion", ""),
        html_url=workflow_run.get("html_url", ""),
        repository_full_name=repository.get("full_name", ""),
        artifacts_url=workflow_run.get("artifacts_url", ""),
    )


def get_installation_id_from_payload(payload: dict[str, Any]) -> int | None:
    """Extract installation ID from webhook payload.

    Args:
        payload: Parsed JSON payload from webhook.

    Returns:
        Installation ID or None.
    """
    installation = payload.get("installation", {})
    return installation.get("id")
