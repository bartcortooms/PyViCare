import unittest
import logging
import io
import subprocess
from unittest.mock import patch, MagicMock
import sys # Required for resetting modules

# Define a name that won't conflict with the actual PyViCare if it's discoverable
# or ensure it's not in sys.modules before the test runs.
PYVICARE_MODULE_NAME = 'PyViCare'

class TestLibraryInitialization(unittest.TestCase):

    def setUp(self):
        self.log_capture_string = io.StringIO()
        self.pyvicare_logger = logging.getLogger(PYVICARE_MODULE_NAME)

        # Store original handlers and level
        self.original_handlers = self.pyvicare_logger.handlers[:]
        self.original_level = self.pyvicare_logger.level
        self.original_propagate = self.pyvicare_logger.propagate

        self.pyvicare_logger.handlers = [] # Clear existing handlers for test isolation
        self.pyvicare_logger.setLevel(logging.INFO)
        self.stream_handler = logging.StreamHandler(self.log_capture_string)
        self.pyvicare_logger.addHandler(self.stream_handler)
        self.pyvicare_logger.propagate = False # Avoid duplicate logs if root logger is also configured

        # Ensure PyViCare is not already imported or reload it
        if PYVICARE_MODULE_NAME in sys.modules:
            del sys.modules[PYVICARE_MODULE_NAME]


    def tearDown(self):
        self.pyvicare_logger.removeHandler(self.stream_handler)
        # Restore original handlers and level
        self.pyvicare_logger.handlers = self.original_handlers
        self.pyvicare_logger.setLevel(self.original_level)
        self.pyvicare_logger.propagate = self.original_propagate

        # Clean up the module from sys.modules to ensure a fresh import next time
        if PYVICARE_MODULE_NAME in sys.modules:
            del sys.modules[PYVICARE_MODULE_NAME]

    @patch('subprocess.run')
    def test_git_commit_logging_success(self, mock_subprocess_run):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "testcommithash123"
        mock_subprocess_run.return_value = mock_process

        # Dynamically import PyViCare to trigger __init__.py
        # This ensures that the __init__.py code runs during the test
        import PyViCare

        log_contents = self.log_capture_string.getvalue()
        self.assertIn("PyViCare library initialized. Git commit: testcommithash123", log_contents)
        mock_subprocess_run.assert_called_once_with(
            ['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=False
        )

    @patch('subprocess.run')
    def test_git_commit_logging_failure_command_error(self, mock_subprocess_run):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "git error"
        mock_subprocess_run.return_value = mock_process

        import PyViCare

        log_contents = self.log_capture_string.getvalue()
        self.assertIn("PyViCare library initialized. Git commit hash could not be determined.", log_contents)
        # Check for the specific error message logged by the __init__.py
        self.assertIn("Failed to get git commit hash. Git process exited with code 1: git error", log_contents)


    @patch('subprocess.run', side_effect=FileNotFoundError("git not found"))
    def test_git_commit_logging_failure_file_not_found(self, mock_subprocess_run):
        import PyViCare

        log_contents = self.log_capture_string.getvalue()
        self.assertIn("PyViCare library initialized. Git commit hash could not be determined.", log_contents)
        self.assertIn("git command not found. Please ensure git is installed and in your system's PATH.", log_contents)

    @patch('subprocess.run')
    def test_git_commit_logging_unexpected_exception(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = Exception("Unexpected subprocess error")

        import PyViCare

        log_contents = self.log_capture_string.getvalue()
        self.assertIn("PyViCare library initialized. Git commit hash could not be determined.", log_contents)
        self.assertIn("An unexpected error occurred while getting git commit hash: Unexpected subprocess error", log_contents)


if __name__ == '__main__':
    unittest.main()
