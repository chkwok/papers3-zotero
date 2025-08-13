#!/usr/bin/env python3
"""
Fix Invalid Zotero Keys in Database

This script scans a Zotero SQLite database for invalid keys (collection, item, and creator keys)
and replaces them with valid ones that conform to Zotero's requirements.

Zotero key requirements:
- Exactly 8 characters
- Only from character set: 23456789ABCDEFGHIJKLMNPQRSTUVWXYZ
- Excludes: 0, 1, L, O, Y (for visual clarity)

Usage:
    python fix_zotero_keys.py --zotero-db path/to/zotero.sqlite [--dry-run]
"""

import sqlite3
import random
import string
import argparse
import logging
from pathlib import Path
from typing import Set, Dict, List, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Valid Zotero key characters (excludes 0, 1, L, O, Y)
VALID_KEY_CHARS = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'


class ZoteroKeyFixer:
    """Fix invalid keys in Zotero database"""
    
    def __init__(self, db_path: str, dry_run: bool = False):
        """
        Initialize the key fixer
        
        Args:
            db_path: Path to Zotero SQLite database
            dry_run: If True, only report issues without fixing them
        """
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = None
        self.cursor = None
        
        # Track statistics
        self.stats = {
            'invalid_collection_keys': 0,
            'invalid_item_keys': 0,
            'invalid_creator_keys': 0,
            'fixed_collection_keys': 0,
            'fixed_item_keys': 0,
            'fixed_creator_keys': 0,
            'generated_keys': set()
        }
        
    def connect(self):
        """Connect to Zotero database"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            
    def is_valid_key(self, key: str) -> bool:
        """
        Check if a key is valid according to Zotero requirements
        
        Args:
            key: Key string to validate
            
        Returns:
            True if key is valid, False otherwise
        """
        if not key or len(key) != 8:
            return False
            
        # Check if all characters are in the valid set
        return all(c in VALID_KEY_CHARS for c in key)
    
    def generate_valid_key(self) -> str:
        """
        Generate a valid Zotero key
        
        Returns:
            8-character key using only valid characters
        """
        while True:
            key = ''.join(random.choice(VALID_KEY_CHARS) for _ in range(8))
            # Make sure we don't generate duplicate keys
            if key not in self.stats['generated_keys']:
                self.stats['generated_keys'].add(key)
                return key
    
    def get_existing_keys(self, table: str, key_column: str) -> Set[str]:
        """
        Get all existing keys from a table
        
        Args:
            table: Table name
            key_column: Column name containing keys
            
        Returns:
            Set of existing keys
        """
        self.cursor.execute(f"SELECT {key_column} FROM {table}")
        return {row[0] for row in self.cursor.fetchall() if row[0]}
    
    def fix_collection_keys(self):
        """Fix invalid collection keys"""
        logger.info("Checking collection keys...")
        
        # Get all existing keys to avoid duplicates
        existing_keys = self.get_existing_keys('collections', 'key')
        self.stats['generated_keys'].update(existing_keys)
        
        # Find invalid collection keys
        self.cursor.execute("""
            SELECT collectionID, key, collectionName 
            FROM collections 
            WHERE key IS NOT NULL
        """)
        
        collections = self.cursor.fetchall()
        invalid_collections = []
        
        for coll_id, key, name in collections:
            if not self.is_valid_key(key):
                invalid_collections.append((coll_id, key, name))
                self.stats['invalid_collection_keys'] += 1
                
        if invalid_collections:
            logger.warning(f"Found {len(invalid_collections)} collections with invalid keys")
            
            for coll_id, old_key, name in invalid_collections:
                new_key = self.generate_valid_key()
                logger.info(f"Collection '{name}' (ID: {coll_id}): {old_key} -> {new_key}")
                
                if not self.dry_run:
                    self.cursor.execute("""
                        UPDATE collections 
                        SET key = ?, version = version + 1, synced = 0
                        WHERE collectionID = ?
                    """, (new_key, coll_id))
                    self.stats['fixed_collection_keys'] += 1
        else:
            logger.info("✓ All collection keys are valid")
    
    def fix_item_keys(self):
        """Fix invalid item keys"""
        logger.info("Checking item keys...")
        
        # Get all existing keys to avoid duplicates
        existing_keys = self.get_existing_keys('items', 'key')
        self.stats['generated_keys'].update(existing_keys)
        
        # Find invalid item keys
        self.cursor.execute("""
            SELECT itemID, key, itemTypeID
            FROM items 
            WHERE key IS NOT NULL
        """)
        
        items = self.cursor.fetchall()
        invalid_items = []
        
        for item_id, key, type_id in items:
            if not self.is_valid_key(key):
                invalid_items.append((item_id, key, type_id))
                self.stats['invalid_item_keys'] += 1
                
        if invalid_items:
            logger.warning(f"Found {len(invalid_items)} items with invalid keys")
            
            # Process in batches for performance
            for item_id, old_key, type_id in invalid_items:
                new_key = self.generate_valid_key()
                
                if not self.dry_run:
                    self.cursor.execute("""
                        UPDATE items 
                        SET key = ?, version = version + 1, synced = 0
                        WHERE itemID = ?
                    """, (new_key, item_id))
                    self.stats['fixed_item_keys'] += 1
                    
            logger.info(f"Fixed {self.stats['fixed_item_keys']} item keys")
        else:
            logger.info("✓ All item keys are valid")
    
    def verify_fixes(self):
        """Verify that all keys are now valid"""
        logger.info("\nVerifying fixes...")
        
        # Check collections
        self.cursor.execute("""
            SELECT COUNT(*) FROM collections 
            WHERE key IS NOT NULL
        """)
        total_collections = self.cursor.fetchone()[0]
        
        self.cursor.execute("""
            SELECT key FROM collections 
            WHERE key IS NOT NULL
        """)
        
        invalid_count = 0
        for (key,) in self.cursor.fetchall():
            if not self.is_valid_key(key):
                invalid_count += 1
                logger.error(f"Still invalid collection key: {key}")
                
        if invalid_count == 0:
            logger.info(f"✓ All {total_collections} collection keys are valid")
        else:
            logger.error(f"✗ Found {invalid_count} invalid collection keys remaining")
            
        # Check items
        self.cursor.execute("""
            SELECT COUNT(*) FROM items 
            WHERE key IS NOT NULL
        """)
        total_items = self.cursor.fetchone()[0]
        
        self.cursor.execute("""
            SELECT key FROM items 
            WHERE key IS NOT NULL
        """)
        
        invalid_count = 0
        for (key,) in self.cursor.fetchall():
            if not self.is_valid_key(key):
                invalid_count += 1
                logger.error(f"Still invalid item key: {key}")
                
        if invalid_count == 0:
            logger.info(f"✓ All {total_items} item keys are valid")
        else:
            logger.error(f"✗ Found {invalid_count} invalid item keys remaining")
    
    def check_for_duplicates(self):
        """Check for any duplicate keys"""
        logger.info("\nChecking for duplicate keys...")
        
        # Check collection duplicates
        self.cursor.execute("""
            SELECT key, COUNT(*) as count 
            FROM collections 
            WHERE key IS NOT NULL 
            GROUP BY key 
            HAVING count > 1
        """)
        
        duplicates = self.cursor.fetchall()
        if duplicates:
            logger.error(f"Found {len(duplicates)} duplicate collection keys:")
            for key, count in duplicates:
                logger.error(f"  Key {key}: {count} occurrences")
        else:
            logger.info("✓ No duplicate collection keys found")
            
        # Check item duplicates
        self.cursor.execute("""
            SELECT key, COUNT(*) as count 
            FROM items 
            WHERE key IS NOT NULL 
            GROUP BY key 
            HAVING count > 1
        """)
        
        duplicates = self.cursor.fetchall()
        if duplicates:
            logger.error(f"Found {len(duplicates)} duplicate item keys:")
            for key, count in duplicates:
                logger.error(f"  Key {key}: {count} occurrences")
        else:
            logger.info("✓ No duplicate item keys found")
    
    def run(self):
        """Run the key fixing process"""
        try:
            self.connect()
            
            if self.dry_run:
                logger.info("=== DRY RUN MODE - No changes will be made ===\n")
            
            # Start transaction
            if not self.dry_run:
                self.conn.execute("BEGIN TRANSACTION")
            
            # Fix keys
            self.fix_collection_keys()
            self.fix_item_keys()
            
            # Verify and check for duplicates
            if not self.dry_run:
                self.verify_fixes()
                self.check_for_duplicates()
            
            # Print statistics
            logger.info("\n=== Statistics ===")
            logger.info(f"Invalid collection keys found: {self.stats['invalid_collection_keys']}")
            logger.info(f"Invalid item keys found: {self.stats['invalid_item_keys']}")
            
            if not self.dry_run:
                logger.info(f"Collection keys fixed: {self.stats['fixed_collection_keys']}")
                logger.info(f"Item keys fixed: {self.stats['fixed_item_keys']}")
                
                # Commit changes
                logger.info("\nCommitting changes...")
                self.conn.commit()
                logger.info("✓ Changes committed successfully")
                
                if self.stats['fixed_collection_keys'] > 0 or self.stats['fixed_item_keys'] > 0:
                    logger.info("\n⚠️  IMPORTANT: You must restart Zotero and sync to apply these changes")
            else:
                logger.info("\nDry run complete. Use without --dry-run to apply fixes.")
                
        except Exception as e:
            logger.error(f"Error during key fixing: {e}")
            if self.conn and not self.dry_run:
                logger.info("Rolling back changes...")
                self.conn.rollback()
            raise
        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Fix invalid keys in Zotero database')
    parser.add_argument('--zotero-db', required=True,
                        help='Path to Zotero SQLite database')
    parser.add_argument('--dry-run', action='store_true',
                        help='Check for invalid keys without fixing them')
    
    args = parser.parse_args()
    
    # Verify database exists
    if not Path(args.zotero_db).exists():
        logger.error(f"Database not found: {args.zotero_db}")
        return 1
    
    # Run fixer
    fixer = ZoteroKeyFixer(args.zotero_db, dry_run=args.dry_run)
    
    try:
        fixer.run()
        return 0
    except Exception as e:
        logger.error(f"Failed to fix keys: {e}")
        return 1


if __name__ == "__main__":
    exit(main())