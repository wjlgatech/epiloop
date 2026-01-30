"""
Dashboard Backend Package
=========================

Flask-based REST API and SSE server for real-time progress monitoring.
"""

from .api import DashboardAPI

__all__ = ['DashboardAPI']
__version__ = '1.0.0'
