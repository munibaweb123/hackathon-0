"""
Configuration Module for Watchers

This module contains configuration settings for the watcher scripts.
"""

import os
from typing import Dict, Any


class WatcherConfig:
    """
    Configuration class for watcher scripts.
    """

    def __init__(self):
        """
        Initialize configuration from environment variables or defaults.
        """
        # Gmail configuration
        self.gmail_oauth_token = os.getenv('GMAIL_OAUTH_TOKEN', '')
        self.gmail_account = os.getenv('GMAIL_ACCOUNT', 'default@gmail.com')
        self.gmail_check_interval = int(os.getenv('GMAIL_CHECK_INTERVAL', '300'))  # 5 minutes

        # LinkedIn configuration
        self.linkedin_api_token = os.getenv('LINKEDIN_API_TOKEN', '')
        self.linkedin_profile_url = os.getenv('LINKEDIN_PROFILE_URL', 'https://linkedin.com/in/default')
        self.linkedin_check_interval = int(os.getenv('LINKEDIN_CHECK_INTERVAL', '600'))  # 10 minutes

        # General configuration
        self.vault_path = os.getenv('VAULT_PATH', './vault')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

    def get_gmail_config(self) -> Dict[str, Any]:
        """
        Get Gmail-specific configuration.

        Returns:
            Dictionary containing Gmail configuration
        """
        return {
            'oauth_token': self.gmail_oauth_token,
            'account': self.gmail_account,
            'check_interval': self.gmail_check_interval
        }

    def get_linkedin_config(self) -> Dict[str, Any]:
        """
        Get LinkedIn-specific configuration.

        Returns:
            Dictionary containing LinkedIn configuration
        """
        return {
            'api_token': self.linkedin_api_token,
            'profile_url': self.linkedin_profile_url,
            'check_interval': self.linkedin_check_interval
        }

    def validate_config(self) -> bool:
        """
        Validate that required configuration is present.

        Returns:
            True if configuration is valid, False otherwise
        """
        # For demo purposes, we'll just check if vault path exists
        import os
        return os.path.exists(self.vault_path)