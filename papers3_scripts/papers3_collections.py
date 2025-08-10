#!/usr/bin/env python3
"""
Papers3 Collection Extractor

This script extracts the hierarchical collection structure from a Papers3 database
and generates a JSON representation with metadata.

Usage:
    python papers3_collections.py [database_path] [--full] [--human-readable] [--include-all]
    
Default database path: Database.papersdb
--full: Export full publication details instead of just UUIDs
--human-readable: Use first 75 characters of title instead of UUIDs
--include-all: Include all collections (default: only children of "COLLECTIONS")
"""

import sqlite3
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


class Papers3CollectionExtractor:
    def __init__(self, database_path: str = "Database.papersdb", full_export: bool = False, human_readable: bool = False, include_all: bool = False):
        self.database_path = database_path
        self.full_export = full_export
        self.human_readable = human_readable
        self.include_all = include_all
        self.collections = {}
        self.collection_items = {}
        
    def connect_database(self) -> sqlite3.Connection:
        """Connect to the Papers3 SQLite database."""
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Database file not found: {self.database_path}")
        
        return sqlite3.connect(self.database_path)
    
    def get_collections(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
        """Extract all collections with their metadata."""
        cursor = conn.cursor()
        
        query = """
        SELECT 
            uuid,
            name,
            collection_description,
            parent,
            priority,
            type,
            privacy_level,
            editable,
            icon_name,
            update_count,
            created_at,
            updated_at,
            configuration
        FROM Collection
        ORDER BY priority, name
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        collections = {}
        for row in rows:
            collection = {
                "uuid": row[0],
                "name": row[1],
                "parent": row[3],
                "priority": row[4],
                "type": row[5],
                "created_at": self._format_timestamp(row[10]),
                "updated_at": self._format_timestamp(row[11]),
                "children": []
            }
            collections[row[0]] = collection
            
        return collections
    
    def get_collection_items(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all collection items with publication metadata."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all publication details
            query = """
            SELECT 
                ci.collection,
                ci.object_id,
                ci.priority,
                ci.privacy_level,
                ci.type,
                ci.created_at,
                ci.updated_at,
                p.title,
                p.author_string,
                p.publication_date,
                p.doi,
                p.publisher,
                p.volume,
                p.startpage,
                p.endpage,
                p.type as pub_type,
                p.rating,
                p.read_status,
                p.flagged,
                p.notes,
                p.keyword_string,
                p.times_cited,
                p.times_read
            FROM CollectionItem ci
            JOIN Publication p ON ci.object_id = p.uuid
            ORDER BY ci.collection, ci.priority, p.title
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            collection_items = {}
            for row in rows:
                item = {
                    "publication_uuid": row[1],
                    "priority": row[2],
                    "privacy_level": row[3],
                    "type": row[4],
                    "created_at": self._format_timestamp(row[5]),
                    "updated_at": self._format_timestamp(row[6]),
                    "title": row[7],
                    "author_string": row[8],
                    "publication_date": row[9],
                    "doi": row[10],
                    "publisher": row[11],
                    "volume": row[12],
                    "startpage": row[13],
                    "endpage": row[14],
                    "pages": f"{row[13]}-{row[14]}" if row[13] and row[14] else None,
                    "publication_type": row[15],
                    "rating": row[16],
                    "read_status": row[17],
                    "flagged": bool(row[18]) if row[18] is not None else False,
                    "notes": row[19],
                    "keyword_string": row[20],
                    "times_cited": row[21],
                    "times_read": row[22]
                }
                
                collection_uuid = row[0]
                if collection_uuid not in collection_items:
                    collection_items[collection_uuid] = []
                collection_items[collection_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally titles
            if self.human_readable:
                query = """
                SELECT 
                    ci.collection,
                    ci.object_id,
                    ci.priority,
                    p.title
                FROM CollectionItem ci
                JOIN Publication p ON ci.object_id = p.uuid
                ORDER BY ci.collection, ci.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                collection_items = {}
                for row in rows:
                    title = row[3] if row[3] else "Untitled"
                    title_preview = title[:75] + "..." if len(title) > 75 else title
                    
                    item = {
                        "publication_uuid": row[1],
                        "title_preview": title_preview,
                        "priority": row[2]
                    }
                    
                    collection_uuid = row[0]
                    if collection_uuid not in collection_items:
                        collection_items[collection_uuid] = []
                    collection_items[collection_uuid].append(item)
            else:
                query = """
                SELECT 
                    ci.collection,
                    ci.object_id,
                    ci.priority
                FROM CollectionItem ci
                ORDER BY ci.collection, ci.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                collection_items = {}
                for row in rows:
                    item = {
                        "publication_uuid": row[1],
                        "priority": row[2]
                    }
                    
                    collection_uuid = row[0]
                    if collection_uuid not in collection_items:
                        collection_items[collection_uuid] = []
                    collection_items[collection_uuid].append(item)
            
        return collection_items
    
    def build_hierarchy(self, collections: Dict[str, Dict[str, Any]], 
                       collection_items: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Build the hierarchical collection structure."""
        # Add items to collections
        for collection_uuid, items in collection_items.items():
            if collection_uuid in collections:
                if self.full_export:
                    collections[collection_uuid]["publications"] = items
                else:
                    if self.human_readable:
                        # For human-readable export, store title previews
                        collections[collection_uuid]["publications"] = [item["title_preview"] for item in items]
                    else:
                        # For lightweight export, just store the UUIDs
                        collections[collection_uuid]["publications"] = [item["publication_uuid"] for item in items]
                collections[collection_uuid]["item_count"] = len(items)
        
        # Build parent-child relationships
        root_collections = []
        
        for collection_uuid, collection in collections.items():
            parent_uuid = collection.get("parent")
            
            if parent_uuid and parent_uuid in collections:
                # This is a child collection
                if "children" not in collections[parent_uuid]:
                    collections[parent_uuid]["children"] = []
                collections[parent_uuid]["children"].append(collection)
            else:
                # This is a root collection
                root_collections.append(collection)
        
        # Filter collections based on include_all parameter
        if not self.include_all:
            # Find the "COLLECTIONS" root collection and only return its children
            collections_root = None
            for collection in root_collections:
                if collection.get("name") == "COLLECTIONS":
                    collections_root = collection
                    break
            
            if collections_root and "children" in collections_root:
                # Remove parent ID from children and set them as root collections
                for child in collections_root["children"]:
                    child["parent"] = None
                
                # Sort children by priority and name
                collections_root["children"].sort(key=lambda x: (x.get("priority", 0), x.get("name", "")))
                return collections_root["children"]
            else:
                return []
        else:
            # Include all collections
            # Sort root collections by priority and name
            root_collections.sort(key=lambda x: (x.get("priority", 0), x.get("name", "")))
            
            # Sort children of each collection by priority and name
            for collection in collections.values():
                if "children" in collection:
                    collection["children"].sort(key=lambda x: (x.get("priority", 0), x.get("name", "")))
            
            return root_collections
    
    def get_collection_statistics(self, collections: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics about the collections."""
        total_collections = len(collections)
        root_collections = sum(1 for c in collections.values() if not c.get("parent"))
        child_collections = total_collections - root_collections
        
        if self.full_export:
            total_items = sum(len(c.get("publications", [])) for c in collections.values())
            collections_with_items = sum(1 for c in collections.values() if c.get("publications"))
        else:
            total_items = sum(len(c.get("publications", [])) for c in collections.values())
            collections_with_items = sum(1 for c in collections.values() if c.get("publications"))
        
        return {
            "total_collections": total_collections,
            "root_collections": root_collections,
            "child_collections": child_collections,
            "collections_with_items": collections_with_items,
            "total_items": total_items,
            "average_items_per_collection": total_items / total_collections if total_collections > 0 else 0
        }
    
    def _format_timestamp(self, timestamp: Optional[float]) -> Optional[str]:
        """Convert Unix timestamp to readable date string."""
        if timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, OSError):
            return str(timestamp)
    
    def extract_collections(self) -> Dict[str, Any]:
        """Main method to extract collection structure and metadata."""
        print(f"Connecting to database: {self.database_path}")
        
        with self.connect_database() as conn:
            print("Extracting collections...")
            collections = self.get_collections(conn)
            
            print("Extracting collection items...")
            collection_items = self.get_collection_items(conn)
            
            print("Building hierarchy...")
            hierarchy = self.build_hierarchy(collections, collection_items)
            
            print("Generating statistics...")
            statistics = self.get_collection_statistics(collections)
            
            result = {
                "metadata": {
                    "database_path": self.database_path,
                    "extraction_date": datetime.now().isoformat(),
                    "statistics": statistics
                },
                "collections": hierarchy
            }
            
            return result
    
    def save_json(self, data: Dict[str, Any], output_path: str = "papers3_collections.json"):
        """Save the collection data to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Collection data saved to: {output_path}")


def main():
    """Main function to run the collection extractor."""
    # Parse command line arguments
    args = sys.argv[1:]
    database_path = "Database.papersdb"
    full_export = False
    human_readable = False
    include_all = False
    
    for arg in args:
        if arg == "--full":
            full_export = True
        elif arg == "--human-readable":
            human_readable = True
        elif arg == "--include-all":
            include_all = True
        elif not arg.startswith("--"):
            database_path = arg
    
    try:
        # Create extractor and extract data
        extractor = Papers3CollectionExtractor(database_path, full_export, human_readable, include_all)
        collection_data = extractor.extract_collections()
        
        # Save to JSON file
        output_file = "papers3_collections.json"
        if full_export:
            output_file = "papers3_collections_full.json"
        elif human_readable:
            output_file = "papers3_collections_human.json"
        if include_all:
            output_file = output_file.replace(".json", "_all.json")
        extractor.save_json(collection_data, output_file)
        
        # Print summary
        stats = collection_data["metadata"]["statistics"]
        if full_export:
            export_type = "Full"
        elif human_readable:
            export_type = "Human-Readable"
        else:
            export_type = "Lightweight"
        scope = "All Collections" if include_all else "COLLECTIONS Children Only"
        print(f"\nExtraction Summary ({export_type} Export, {scope}):")
        print(f"  Total collections: {stats['total_collections']}")
        print(f"  Root collections: {stats['root_collections']}")
        print(f"  Child collections: {stats['child_collections']}")
        print(f"  Collections with items: {stats['collections_with_items']}")
        print(f"  Total items: {stats['total_items']}")
        print(f"  Average items per collection: {stats['average_items_per_collection']:.1f}")
        print(f"  Output file: {output_file}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 