#!/usr/bin/env python3
"""Script to check database migration status."""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import artfight_rss
sys.path.insert(0, str(Path(__file__).parent.parent))

from artfight_rss.database import ArtFightDatabase
from artfight_rss.config import settings
import json


def main():
    """Check and display database migration status."""
    # Initialize database
    db_path = Path(settings.database_path)
    database = ArtFightDatabase(db_path)
    
    # Get migration status
    migration_status = database.get_migration_status()
    
    print("Database Migration Status")
    print("=" * 50)
    print(f"Database: {migration_status['database_path']}")
    print(f"Total Applied Migrations: {migration_status['total_applied']}")
    print(f"Latest Migration: {migration_status['latest_migration']}")
    print()
    
    if 'error' in migration_status:
        print(f"Error: {migration_status['error']}")
        return
    
    if migration_status['applied_migrations']:
        print("Applied Migrations:")
        print("-" * 30)
        for migration in migration_status['applied_migrations']:
            print(f"  {migration['number']:2d}. {migration['name']}")
            print(f"      Applied: {migration['applied_at']}")
            print(f"      Description: {migration['description']}")
            print()
    else:
        print("No migrations have been applied yet.")
    
    # Check for pending migrations
    pending_migrations = database.get_pending_migrations()
    if pending_migrations:
        print("Pending Migrations:")
        print("-" * 30)
        for migration in pending_migrations:
            print(f"  {migration['number']:2d}. {migration['name']}")
            print(f"      Description: {migration['description']}")
            if 'columns' in migration:
                print(f"      Columns: {', '.join(migration['columns'].keys())}")
            print()
        
        # Ask if user wants to run migrations
        response = input("Run pending migrations? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            print("\nRunning migrations...")
            results = database.run_migrations_manually()
            
            print("\nMigration Results:")
            print("-" * 30)
            
            if results['applied_migrations']:
                print("Applied Migrations:")
                for migration in results['applied_migrations']:
                    print(f"  {migration['number']:2d}. {migration['name']} - {migration['status']}")
                    if 'added_columns' in migration and migration['added_columns']:
                        print(f"      Added columns: {', '.join(migration['added_columns'])}")
                    if 'message' in migration:
                        print(f"      Note: {migration['message']}")
            
            if results['skipped_migrations']:
                print("\nSkipped Migrations:")
                for migration in results['skipped_migrations']:
                    print(f"  {migration['number']:2d}. {migration['name']} - {migration['reason']}")
            
            if results['errors']:
                print("\nErrors:")
                for error in results['errors']:
                    if 'migration' in error:
                        print(f"  Migration {error['migration']}: {error['error']}")
                    else:
                        print(f"  {error['error']}")
        else:
            print("Migrations not run.")
    else:
        print("No pending migrations.")
    
    # Also show full database stats
    print("\nFull Database Statistics:")
    print("=" * 50)
    stats = database.get_stats()
    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main() 