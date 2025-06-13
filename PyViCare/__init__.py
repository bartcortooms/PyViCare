import logging
import subprocess

# Configure basic logging if no handlers are configured
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

def get_git_commit_hash():
    """Retrieves the current git commit hash."""
    try:
        process = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=False,
            # Ensure git commands are run in the context of the repository if needed
            # cwd='/app' # Assuming /app is the root of the git repository
        )
        if process.returncode == 0:
            return process.stdout.strip()
        else:
            logger.error(f"Failed to get git commit hash. Git process exited with code {process.returncode}: {process.stderr.strip()}")
            return None
    except FileNotFoundError:
        logger.error("git command not found. Please ensure git is installed and in your system's PATH.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting git commit hash: {e}")
        return None

commit_hash = get_git_commit_hash()

if commit_hash:
    logger.info(f"PyViCare library initialized. Git commit: {commit_hash}")
else:
    logger.info("PyViCare library initialized. Git commit hash could not be determined.")

# Placeholder for any other PyViCare initializations
# For example:
# from .PyViCareDevice import Device
# from .PyViCareService import ViCareService
# print("PyViCare components loaded")
