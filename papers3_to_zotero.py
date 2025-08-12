#!/usr/bin/env python3
"""
Papers3 to Zotero Direct Database Migration Script

This script migrates a Papers3 library to Zotero by directly writing to the Zotero SQLite database.
It preserves collections, attachments, tags, and all metadata.

Copyright (c) 2025 Chi Ho Kwok and Contributors
Licensed under the MIT License - see LICENSE file for details

Usage:
    python papers3_to_zotero.py [--test] [--limit N]
"""

import sqlite3
import json
import sys
import os
import random
import string
import re
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Papers3ToZoteroMigrator:
    """Migrates Papers3 library to Zotero database"""
    
    # Item type mappings from Papers3 to Zotero
    ITEM_TYPE_MAP = {
        'article': 22,           # journalArticle
        'periodical': 22,        # treat as journalArticle container
        'book': 7,               # book
        'report': 34,            # report
        'patent': 29,            # patent
        'media': 14,             # document
        'conference': 11,        # conferencePaper
        'website': 40,           # webpage
        'manual': 14,            # document
        'thesis': 37,            # thesis
    }
    
    # Field IDs in Zotero
    FIELD_IDS = {
        'title': 1,
        'abstractNote': 2,
        'date': 6,
        'url': 13,
        'extra': 16,
        'volume': 19,
        'pages': 32,
        'DOI': 59,
        'issue': 76,
        'publicationTitle': 5,
        'publisher': 20,
        'place': 7,
        'ISBN': 69,
        'ISSN': 71,
        'language': 78,
        'shortTitle': 115,
        'accessDate': 65,
    }
    
    # Creator type mappings
    CREATOR_TYPE_MAP = {
        'author': 8,
        'editor': 10,
        'translator': 11,
        'contributor': 2,
    }
    
    def __init__(self, catalog_path: str, zotero_db_path: str, 
                 test_mode: bool = False, limit: Optional[int] = None,
                 skip_attachments: bool = False, files_dir: Optional[str] = None,
                 files_target_dir: Optional[str] = None, files_only: bool = False):
        """
        Initialize the migrator
        
        Args:
            catalog_path: Path to Papers3 JSON catalog directory
            zotero_db_path: Path to Zotero SQLite database
            test_mode: If True, changes won't be committed
            limit: Limit number of items to import (for testing)
            skip_attachments: If True, skip PDF attachment import
            files_dir: Path to Papers3 Files directory with hex subdirectories
            files_target_dir: Destination directory for human-readable file structure
            files_only: If True, only copy files without database migration
        """
        self.catalog_path = Path(catalog_path)
        self.zotero_db_path = zotero_db_path
        self.test_mode = test_mode
        self.limit = limit
        self.skip_attachments = skip_attachments
        self.files_dir = Path(files_dir) if files_dir else None
        self.files_target_dir = Path(files_target_dir) if files_target_dir else None
        self.files_only = files_only
        
        # Maps for tracking IDs
        self.collection_map: Dict[str, int] = {}  # Papers3 UUID -> Zotero ID
        self.item_map: Dict[str, int] = {}        # Papers3 UUID -> Zotero ID
        self.creator_map: Dict[str, int] = {}     # Creator name -> Zotero ID
        self.tag_map: Dict[str, int] = {}         # Tag name -> Zotero ID
        
        # Statistics
        self.stats = {
            'collections': 0,
            'items': 0,
            'attachments': 0,
            'creators': 0,
            'tags': 0,
            'errors': [],
            'files_found': 0,
            'files_copied': 0,
            'files_skipped': 0,
            'files_missing': 0,
            'missing_files': []
        }
        
    def validate_files_directory(self):
        """Validate that the Files directory has the expected hex structure"""
        if not self.files_dir or not self.files_dir.exists():
            return False
            
        # Check for at least some hex directories (00-FF)
        hex_dirs = []
        for hex_val in ['00', '01', '02', '0A', '0F', '10', '1F', 'A0', 'FF']:
            if (self.files_dir / hex_val).exists():
                hex_dirs.append(hex_val)
                
        if len(hex_dirs) < 1:
            logger.warning(f"Files directory appears invalid. Found no hex subdirectories")
            return False
            
        logger.info(f"Files directory validated. Found hex subdirectories: {', '.join(hex_dirs[:5])}...")
        return True
    
    def sanitize_filename(self, filename: str, max_length: int = 100) -> str:
        """Sanitize filename for filesystem compatibility"""
        if not filename:
            return "Unknown"
            
        # Replace invalid characters
        invalid_chars = '<>:"|?*\\/\0'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
            
        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Truncate to max length
        if len(filename) > max_length:
            filename = filename[:max_length].rstrip(' .')
            
        # Fallback if empty after sanitization
        if not filename:
            filename = "Unknown"
            
        return filename
    
    def compute_file_hash(self, file_path: Path, quick: bool = False) -> str:
        """Compute MD5 hash of a file
        
        Args:
            file_path: Path to the file
            quick: If True, only hash first 1MB for quick comparison
            
        Returns:
            MD5 hash as hex string
        """
        hash_md5 = hashlib.md5()
        chunk_size = 8192
        max_bytes = 1024 * 1024 if quick else None  # 1MB for quick hash
        bytes_read = 0
        
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hash_md5.update(chunk)
                    bytes_read += len(chunk)
                    if max_bytes and bytes_read >= max_bytes:
                        break
            return hash_md5.hexdigest()
        except Exception as e:
            logger.debug(f"Error computing hash for {file_path}: {e}")
            return ""
    
    def files_are_identical(self, path1: Path, path2: Path) -> bool:
        """Check if two files are identical
        
        First checks file size, then compares MD5 hashes
        """
        try:
            # Quick check: file size
            if path1.stat().st_size != path2.stat().st_size:
                return False
            
            # Full check: MD5 hash
            return self.compute_file_hash(path1) == self.compute_file_hash(path2)
        except Exception as e:
            logger.debug(f"Error comparing files: {e}")
            return False
    
    def build_base_path(self, pub: Dict, pdf: Dict) -> Path:
        """Build a base human-readable file path for a PDF (without collision handling)"""
        # Extract year
        pub_date = pub.get('publication_date')
        if pub_date:
            try:
                if 'T' in str(pub_date):
                    year = pub_date.split('-')[0]
                elif len(str(pub_date)) == 4:
                    year = str(pub_date)
                else:
                    year = "Unknown"
            except:
                year = "Unknown"
        else:
            year = "Unknown"
            
        # Extract first author's last name
        authors = pub.get('authors', [])
        if authors and len(authors) > 0:
            first_author = authors[0]
            if isinstance(first_author, dict):
                author_name = first_author.get('surname') or first_author.get('fullname', 'NoAuthor')
            else:
                # Try to parse string format
                author_str = str(first_author)
                if ', ' in author_str:
                    author_name = author_str.split(', ')[0]
                else:
                    author_name = author_str
            author_name = self.sanitize_filename(author_name, 50)
        else:
            author_name = "NoAuthor"
            
        # Build filename from title
        title = pub.get('title', 'Untitled')
        title = self.sanitize_filename(title)
        
        # Get file extension
        if isinstance(pdf, dict):
            original_path = pdf.get('path') or pdf.get('original_path', '')
            extension = Path(original_path).suffix or '.pdf'
        else:
            extension = '.pdf'
            
        # Build base filename
        base_filename = f"{title}_{year}{extension}"
        
        # Build full path
        return self.files_target_dir / year / author_name / base_filename
    
    def find_available_path(self, source_path: Path, base_target_path: Path, pub_uuid: str) -> Tuple[Path, bool]:
        """Find an available path for the file, checking for duplicates
        
        Returns:
            Tuple of (target_path, is_duplicate)
            - target_path: Where to copy the file (or where it already exists)
            - is_duplicate: True if file already exists at some path
        """
        # Check if base path is available or contains our file
        if not base_target_path.exists():
            return base_target_path, False
        elif self.files_are_identical(source_path, base_target_path):
            return base_target_path, True
        
        # Try numbered variants
        stem = base_target_path.stem
        suffix = base_target_path.suffix
        parent = base_target_path.parent
        
        for counter in range(2, 11):  # Try _2 through _10
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path, False
            elif self.files_are_identical(source_path, new_path):
                return new_path, True
        
        # Too many collisions, use UUID
        uuid_path = parent / f"{pub_uuid}{suffix}"
        if uuid_path.exists() and self.files_are_identical(source_path, uuid_path):
            return uuid_path, True
        return uuid_path, False
    
    def connect_databases(self):
        """Connect to Zotero database"""
        if not self.files_only:
            self.zotero_conn = sqlite3.connect(self.zotero_db_path)
            self.zotero_conn.execute("PRAGMA foreign_keys = ON")
            self.zotero_cursor = self.zotero_conn.cursor()
        
    def load_papers3_data(self):
        """Load Papers3 JSON exports"""
        logger.info("Loading Papers3 data...")
        
        # Load publications (prefer full version if available)
        pub_file_full = self.catalog_path / 'papers3_publications_full.json'
        pub_file = self.catalog_path / 'papers3_publications.json'
        
        if pub_file_full.exists():
            with open(pub_file_full, 'r', encoding='utf-8') as f:
                self.papers3_data = json.load(f)
                logger.info(f"Loaded {len(self.papers3_data['publications'])} publications from full export")
        elif pub_file.exists():
            with open(pub_file, 'r', encoding='utf-8') as f:
                self.papers3_data = json.load(f)
                logger.info(f"Loaded {len(self.papers3_data['publications'])} publications")
        else:
            raise FileNotFoundError(
                f"Required publication file not found. Need either:\n"
                f"  - {pub_file_full}\n"
                f"  - {pub_file}"
            )
        
        # Load collections if available
        coll_file = self.catalog_path / 'papers3_collections.json'
        if coll_file.exists():
            with open(coll_file, 'r', encoding='utf-8') as f:
                self.collections_data = json.load(f)
                logger.info(f"Loaded {len(self.collections_data['collections'])} collections")
        else:
            logger.info("No collections file found, skipping collection import")
            self.collections_data = {'collections': []}
            
    def generate_key(self, length: int = 8) -> str:
        """Generate a Zotero-style key"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def migrate_collections(self):
        """Migrate collection hierarchy"""
        logger.info("Migrating collections...")
        
        def get_or_create_collection(name: str, parent_id: Optional[int] = None) -> int:
            """Get existing collection or create new one"""
            # Check if collection exists with same name and parent
            if parent_id:
                self.zotero_cursor.execute("""
                    SELECT collectionID FROM collections 
                    WHERE collectionName = ? AND parentCollectionID = ? AND libraryID = 1
                """, (name, parent_id))
            else:
                self.zotero_cursor.execute("""
                    SELECT collectionID FROM collections 
                    WHERE collectionName = ? AND parentCollectionID IS NULL AND libraryID = 1
                """, (name,))
            
            result = self.zotero_cursor.fetchone()
            if result:
                return result[0]
            
            # Create new collection
            self.zotero_cursor.execute("""
                INSERT INTO collections 
                (collectionName, parentCollectionID, libraryID, key, version, synced)
                VALUES (?, ?, 1, ?, 0, 0)
            """, (name, parent_id, self.generate_key()))
            
            self.stats['collections'] += 1
            return self.zotero_cursor.lastrowid
        
        def import_collection(collection: Dict, parent_id: Optional[int] = None):
            """Recursively import collection and its children"""
            try:
                # Get or create collection
                coll_id = get_or_create_collection(collection['name'], parent_id)
                self.collection_map[collection['uuid']] = coll_id
                
                # Import children
                for child in collection.get('children', []):
                    import_collection(child, coll_id)
                    
            except Exception as e:
                logger.error(f"Error importing collection {collection.get('name')}: {e}")
                self.stats['errors'].append(f"Collection: {e}")
        
        # Import root collections
        for collection in self.collections_data['collections']:
            import_collection(collection)
            
        logger.info(f"Imported {self.stats['collections']} collections")
    
    def parse_papers3_date(self, date_str: Optional[str]) -> Optional[str]:
        """Convert Papers3 date to Zotero format"""
        if not date_str:
            return None
            
        try:
            # ISO format from Papers3 export
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            # Year only
            elif len(date_str) == 4 and date_str.isdigit():
                return date_str
            else:
                return date_str
        except:
            return None
    
    def parse_authors(self, author_list: List) -> List[Tuple[str, str, str]]:
        """Parse Papers3 authors into (firstName, lastName, creatorType)"""
        creators = []
        
        for author in author_list:
            if isinstance(author, dict):
                first = author.get('prename', '')
                last = author.get('surname', author.get('fullname', ''))
                creator_type = author.get('type', 'author')
            else:
                # Simple string format
                parts = str(author).split(', ')
                if len(parts) == 2:
                    last, first = parts
                else:
                    first = ''
                    last = str(author)
                creator_type = 'author'
                
            creators.append((first, last, creator_type))
            
        return creators
    
    def get_or_create_creator(self, firstName: str, lastName: str) -> int:
        """Get existing creator ID or create new creator"""
        key = f"{firstName}|{lastName}"
        
        if key in self.creator_map:
            return self.creator_map[key]
            
        # Check if creator exists
        self.zotero_cursor.execute("""
            SELECT creatorID FROM creators 
            WHERE firstName = ? AND lastName = ?
        """, (firstName, lastName))
        
        result = self.zotero_cursor.fetchone()
        if result:
            creator_id = result[0]
        else:
            # Create new creator
            self.zotero_cursor.execute("""
                INSERT INTO creators (firstName, lastName, fieldMode)
                VALUES (?, ?, 0)
            """, (firstName, lastName))
            creator_id = self.zotero_cursor.lastrowid
            self.stats['creators'] += 1
            
        self.creator_map[key] = creator_id
        return creator_id
    
    def get_or_create_tag(self, tag_name: str) -> int:
        """Get existing tag ID or create new tag"""
        if tag_name in self.tag_map:
            return self.tag_map[tag_name]
            
        # Check if tag exists
        self.zotero_cursor.execute("""
            SELECT tagID FROM tags WHERE name = ?
        """, (tag_name,))
        
        result = self.zotero_cursor.fetchone()
        if result:
            tag_id = result[0]
        else:
            # Create new tag
            self.zotero_cursor.execute("""
                INSERT INTO tags (name) VALUES (?)
            """, (tag_name,))
            tag_id = self.zotero_cursor.lastrowid
            self.stats['tags'] += 1
            
        self.tag_map[tag_name] = tag_id
        return tag_id
    
    def add_item_data(self, item_id: int, field_name: str, value: Any):
        """Add field data to item"""
        if value is None or value == '':
            return
            
        field_id = self.FIELD_IDS.get(field_name)
        if not field_id:
            return
            
        # Check if value exists in itemDataValues
        self.zotero_cursor.execute("""
            SELECT valueID FROM itemDataValues WHERE value = ?
        """, (str(value),))
        
        result = self.zotero_cursor.fetchone()
        if result:
            value_id = result[0]
        else:
            # Create new value
            self.zotero_cursor.execute("""
                INSERT INTO itemDataValues (value) VALUES (?)
            """, (str(value),))
            value_id = self.zotero_cursor.lastrowid
            
        # Link to item
        try:
            self.zotero_cursor.execute("""
                INSERT INTO itemData (itemID, fieldID, valueID)
                VALUES (?, ?, ?)
            """, (item_id, field_id, value_id))
        except sqlite3.IntegrityError:
            # Field already exists for this item
            pass
    
    def migrate_publication(self, pub: Dict) -> Optional[int]:
        """Migrate a single publication"""
        try:
            # Map item type
            pub_type = pub.get('type', 'article')
            item_type_id = self.ITEM_TYPE_MAP.get(pub_type, 14)  # Default to document
            
            # Create timestamps
            date_added = pub.get('created_at', datetime.now().isoformat())
            date_modified = pub.get('updated_at', date_added)
            
            # Create item
            self.zotero_cursor.execute("""
                INSERT INTO items 
                (itemTypeID, libraryID, key, dateAdded, dateModified, version, synced)
                VALUES (?, 1, ?, ?, ?, 0, 0)
            """, (item_type_id, self.generate_key(), 
                  date_added, date_modified))
            
            item_id = self.zotero_cursor.lastrowid
            self.item_map[pub['uuid']] = item_id
            
            # Add basic fields
            self.add_item_data(item_id, 'title', pub.get('title'))
            self.add_item_data(item_id, 'abstractNote', pub.get('summary') or pub.get('notes'))
            self.add_item_data(item_id, 'date', self.parse_papers3_date(pub.get('publication_date')))
            self.add_item_data(item_id, 'DOI', pub.get('doi'))
            self.add_item_data(item_id, 'url', pub.get('url'))
            self.add_item_data(item_id, 'volume', pub.get('volume'))
            self.add_item_data(item_id, 'issue', pub.get('number'))
            self.add_item_data(item_id, 'publisher', pub.get('publisher'))
            self.add_item_data(item_id, 'language', pub.get('language'))
            
            # Handle pages
            if pub.get('startpage') and pub.get('endpage'):
                pages = f"{pub['startpage']}-{pub['endpage']}"
                self.add_item_data(item_id, 'pages', pages)
            elif pub.get('pages'):
                self.add_item_data(item_id, 'pages', pub['pages'])
            
            # Handle bundle (journal name for articles)
            if pub.get('bundle_details'):
                self.add_item_data(item_id, 'publicationTitle', pub['bundle_details'].get('title'))
            
            # Add Papers3-specific data to Extra field
            extra_parts = []
            if pub.get('rating'):
                extra_parts.append(f"Rating: {pub['rating']}/5")
            if pub.get('read_status'):
                extra_parts.append(f"Read Status: {pub['read_status']}")
            if pub.get('times_cited'):
                extra_parts.append(f"Times Cited: {pub['times_cited']}")
            extra_parts.append(f"Papers3 UUID: {pub['uuid']}")
            
            if extra_parts:
                self.add_item_data(item_id, 'extra', '\n'.join(extra_parts))
            
            # Add creators
            if pub.get('authors'):
                creators = self.parse_authors(pub['authors'])
                for idx, (first, last, creator_type) in enumerate(creators):
                    creator_id = self.get_or_create_creator(first, last)
                    creator_type_id = self.CREATOR_TYPE_MAP.get(creator_type, 8)
                    
                    self.zotero_cursor.execute("""
                        INSERT INTO itemCreators 
                        (itemID, creatorID, creatorTypeID, orderIndex)
                        VALUES (?, ?, ?, ?)
                    """, (item_id, creator_id, creator_type_id, idx))
            
            # Add tags
            if pub.get('keywords'):
                added_tags = set()  # Track tags already added to this item
                for keyword in pub['keywords']:
                    if isinstance(keyword, dict):
                        tag_name = keyword.get('name', '')
                    else:
                        tag_name = str(keyword)
                    
                    if tag_name and tag_name not in added_tags:
                        tag_id = self.get_or_create_tag(tag_name)
                        added_tags.add(tag_name)
                        
                        try:
                            self.zotero_cursor.execute("""
                                INSERT INTO itemTags (itemID, tagID, type)
                                VALUES (?, ?, 0)
                            """, (item_id, tag_id))
                        except sqlite3.IntegrityError:
                            # Tag already linked to this item, skip
                            pass
            
            # Add to collections
            if pub.get('collections'):
                for collection in pub['collections']:
                    if isinstance(collection, dict):
                        coll_uuid = collection.get('collection_uuid')
                    else:
                        coll_uuid = str(collection)
                    
                    if coll_uuid in self.collection_map:
                        self.zotero_cursor.execute("""
                            INSERT INTO collectionItems 
                            (collectionID, itemID, orderIndex)
                            VALUES (?, ?, 0)
                        """, (self.collection_map[coll_uuid], item_id))
            
            # Add flagged tag if needed
            if pub.get('flagged'):
                if 'added_tags' not in locals():
                    added_tags = set()
                if 'Flagged' not in added_tags:
                    tag_id = self.get_or_create_tag('Flagged')
                    try:
                        self.zotero_cursor.execute("""
                            INSERT INTO itemTags (itemID, tagID, type)
                            VALUES (?, ?, 0)
                        """, (item_id, tag_id))
                    except sqlite3.IntegrityError:
                        pass
            
            self.stats['items'] += 1
            return item_id
            
        except Exception as e:
            logger.error(f"Error migrating publication {pub.get('uuid')}: {e}")
            self.stats['errors'].append(f"Publication {pub.get('uuid')}: {e}")
            return None
    
    def copy_and_organize_file(self, source_path: Path, target_path: Path, pub_uuid: str) -> Optional[Path]:
        """Copy a file from source to target with smart duplicate detection
        
        Returns:
            Path where file exists (either newly copied or already present), or None if failed
        """
        try:
            # Check if source exists
            if not source_path.exists():
                self.stats['files_missing'] += 1
                self.stats['missing_files'].append(str(source_path))
                return None
                
            self.stats['files_found'] += 1
            
            # Find available path or detect duplicate
            final_path, is_duplicate = self.find_available_path(source_path, target_path, pub_uuid)
            
            if is_duplicate:
                self.stats['files_skipped'] += 1
                logger.debug(f"File already exists at: {final_path}")
                return final_path
                
            # Create target directory if needed
            final_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file (or simulate in test mode)
            if not self.test_mode:
                shutil.copy2(source_path, final_path)
                logger.debug(f"Copied: {source_path} -> {final_path}")
            else:
                logger.debug(f"Would copy: {source_path} -> {final_path}")
                
            self.stats['files_copied'] += 1
            return final_path
            
        except Exception as e:
            logger.error(f"Error copying file {source_path}: {e}")
            self.stats['errors'].append(f"File copy error: {e}")
            return None
    
    def migrate_pdfs(self, pub: Dict, parent_item_id: Optional[int] = None):
        """Migrate PDF attachments for a publication"""
        if self.skip_attachments:
            return
            
        if not pub.get('pdfs'):
            return
            
        for pdf in pub['pdfs']:
            try:
                if isinstance(pdf, dict):
                    pdf_path = pdf.get('path') or pdf.get('original_path')
                    pdf_caption = pdf.get('caption', 'PDF')
                else:
                    continue
                    
                if not pdf_path:
                    continue
                
                # Handle file copying if directories are specified
                final_path = pdf_path  # Default to original path
                if self.files_dir and self.files_target_dir:
                    # Build source path
                    if pdf_path.startswith('Files/'):
                        # Remove 'Files/' prefix and join with files_dir
                        relative_path = pdf_path[6:]  # Remove 'Files/'
                        source_path = self.files_dir / relative_path
                    else:
                        # Assume it's already a full path
                        source_path = Path(pdf_path)
                        
                    # Build target path with human-readable structure
                    base_target_path = self.build_base_path(pub, pdf)
                    
                    # Copy file with smart duplicate detection
                    result_path = self.copy_and_organize_file(source_path, base_target_path, pub['uuid'])
                    if result_path:
                        final_path = str(result_path.absolute())
                    else:
                        # If copy failed, skip this attachment
                        logger.warning(f"Skipping attachment due to copy failure: {pdf_path}")
                        continue
                
                # Add to database if not in files-only mode
                if not self.files_only and parent_item_id:
                    # Create attachment item
                    self.zotero_cursor.execute("""
                        INSERT INTO items 
                        (itemTypeID, libraryID, key, dateAdded, dateModified, version, synced)
                        VALUES (3, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0)
                    """, (self.generate_key(),))
                    
                    attachment_id = self.zotero_cursor.lastrowid
                    
                    # Add attachment details (linked file mode)
                    self.zotero_cursor.execute("""
                        INSERT INTO itemAttachments
                        (itemID, parentItemID, linkMode, contentType, path)
                        VALUES (?, ?, 2, 'application/pdf', ?)
                    """, (attachment_id, parent_item_id, final_path))
                    
                    # Add title
                    self.add_item_data(attachment_id, 'title', pdf_caption)
                    
                    self.stats['attachments'] += 1
                
            except Exception as e:
                logger.error(f"Error processing PDF attachment: {e}")
                self.stats['errors'].append(f"PDF attachment: {e}")
    
    def migrate(self):
        """Run the complete migration"""
        logger.info("Starting Papers3 to Zotero migration...")
        
        # Validate files directory if specified
        if self.files_dir:
            if not self.validate_files_directory():
                logger.error("Files directory validation failed")
                sys.exit(1)
                
        # Check if we need target directory
        if self.files_dir and not self.files_target_dir:
            logger.error("--files-target-dir is required when --files-dir is specified")
            sys.exit(1)
            
        try:
            # Load Papers3 data
            self.load_papers3_data()
            
            # Files-only mode
            if self.files_only:
                logger.info("Running in files-only mode (no database changes)")
                
                publications = self.papers3_data['publications']
                if self.limit:
                    publications = publications[:self.limit]
                    logger.info(f"Limiting to {self.limit} publications")
                    
                logger.info(f"Processing {len(publications)} publications for file organization...")
                
                for idx, pub in enumerate(publications):
                    if idx % 100 == 0:
                        logger.info(f"Progress: {idx}/{len(publications)}")
                    
                    # Process PDFs without database operations
                    self.migrate_pdfs(pub, None)
                    
                logger.info("✓ File organization completed!")
                
            else:
                # Normal migration mode
                # Connect to databases
                self.connect_databases()
                
                # Start transaction
                self.zotero_conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Migrate collections first
                    if self.collections_data['collections']:
                        self.migrate_collections()
                    
                    # Migrate publications
                    publications = self.papers3_data['publications']
                    if self.limit:
                        publications = publications[:self.limit]
                        logger.info(f"Limiting import to {self.limit} items")
                    
                    logger.info(f"Migrating {len(publications)} publications...")
                    if self.skip_attachments:
                        logger.info("⚠️  Skipping PDF attachments (metadata-only import)")
                    elif self.files_dir:
                        logger.info(f"📁 Organizing files to: {self.files_target_dir}")
                    
                    for idx, pub in enumerate(publications):
                        if idx % 100 == 0:
                            logger.info(f"Progress: {idx}/{len(publications)}")
                        
                        item_id = self.migrate_publication(pub)
                        
                        # Add PDFs if item was created successfully
                        if item_id and not self.skip_attachments:
                            self.migrate_pdfs(pub, item_id)
                    
                    # Commit or rollback based on mode
                    if self.test_mode:
                        logger.info("Test mode: Rolling back changes")
                        self.zotero_conn.rollback()
                    else:
                        logger.info("Committing changes...")
                        self.zotero_conn.commit()
                        logger.info("✓ Migration completed successfully!")
                        
                except Exception as e:
                    # Any error causes full rollback
                    logger.error(f"Migration failed: {e}")
                    logger.info("Rolling back all changes...")
                    self.zotero_conn.rollback()
                    raise
                
            # Print statistics
            logger.info("\n=== Migration Statistics ===")
            if not self.files_only:
                logger.info(f"Collections imported: {self.stats['collections']}")
                logger.info(f"Items imported: {self.stats['items']}")
                logger.info(f"Attachments imported: {self.stats['attachments']}")
                logger.info(f"Creators created: {self.stats['creators']}")
                logger.info(f"Tags created: {self.stats['tags']}")
            
            # File statistics
            if self.files_dir:
                logger.info("\n=== File Operations Statistics ===")
                logger.info(f"Files found and copied: {self.stats['files_copied']}")
                logger.info(f"Files skipped (already exist): {self.stats['files_skipped']}")
                logger.info(f"Files missing from source: {self.stats['files_missing']}")
                
                # Log missing files
                if self.stats['missing_files']:
                    missing_log = 'migration_missing_files.log'
                    with open(missing_log, 'w') as f:
                        for missing in self.stats['missing_files']:
                            f.write(f"{missing}\n")
                    logger.info(f"Missing files logged to: {missing_log}")
            
            if self.stats['errors']:
                logger.warning(f"\n=== Errors ({len(self.stats['errors'])}) ===")
                for error in self.stats['errors'][:10]:
                    logger.warning(error)
                if len(self.stats['errors']) > 10:
                    logger.warning(f"... and {len(self.stats['errors']) - 10} more errors")
            
        finally:
            if hasattr(self, 'zotero_conn'):
                self.zotero_conn.close()


def main():
    parser = argparse.ArgumentParser(description='Migrate Papers3 library to Zotero')
    parser.add_argument('--json-catalog', required=True,
                        help='Path to Papers3 JSON catalog directory containing exported files '
                             '(required files: papers3_publications.json or papers3_publications_full.json; '
                             'optional: papers3_collections.json)')
    parser.add_argument('--files-dir', required=True,
                        help='Path to Papers3 Files directory containing hex subdirectories (00-FF) with attachment files')
    parser.add_argument('--files-target-dir', required=True,
                        help='Destination directory for organized files in human-readable structure (Year/Author/Title format)')
    parser.add_argument('--zotero-db', default='zotero.sqlite',
                        help='Path to Zotero SQLite database (default: zotero.sqlite)')
    parser.add_argument('--files-only', action='store_true',
                        help='Only copy and organize files without database migration')
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode (simulates file operations, no changes committed)')
    parser.add_argument('--limit', type=int,
                        help='Limit number of items to import (for testing)')
    parser.add_argument('--skip-attachments', action='store_true',
                        help='Skip PDF attachment import (metadata only)')
    
    args = parser.parse_args()
    
    # Verify catalog directory exists
    if not os.path.exists(args.json_catalog):
        logger.error(f"Catalog directory not found: {args.json_catalog}")
        sys.exit(1)
    
    # Check for required JSON files
    catalog_path = Path(args.json_catalog)
    pub_file = catalog_path / 'papers3_publications.json'
    pub_file_full = catalog_path / 'papers3_publications_full.json'
    
    if not pub_file.exists() and not pub_file_full.exists():
        logger.error(f"Required publication file not found in {args.json_catalog}")
        logger.error(f"Need either papers3_publications.json or papers3_publications_full.json")
        sys.exit(1)
    
    # Verify Files directory exists if specified
    if not os.path.exists(args.files_dir):
        logger.error(f"Files directory not found: {args.files_dir}")
        sys.exit(1)
    
    # Verify Zotero database exists (unless in files-only mode)
    if not args.files_only and not os.path.exists(args.zotero_db):
        logger.error(f"Zotero database not found: {args.zotero_db}")
        sys.exit(1)
    
    # Check for conflicting options
    if args.skip_attachments and args.files_dir:
        logger.error("Cannot use --skip-attachments with --files-dir")
        sys.exit(1)
    
    # Run migration
    migrator = Papers3ToZoteroMigrator(
        args.json_catalog,
        args.zotero_db,
        test_mode=args.test,
        limit=args.limit,
        skip_attachments=args.skip_attachments,
        files_dir=args.files_dir,
        files_target_dir=args.files_target_dir,
        files_only=args.files_only
    )
    
    migrator.migrate()


if __name__ == "__main__":
    main()