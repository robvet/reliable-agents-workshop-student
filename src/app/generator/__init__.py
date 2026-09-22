"""Synthetic data generator for the utility grid schema.

Package boundary: this is the only feature in the app that writes to
PostgreSQL directly via SQLAlchemy (see src/app/data). Everything else in
the app reads/writes through MCP.
"""

from .spatial_data_generator import SpatialDataGenerator

__all__ = ["SpatialDataGenerator"]
