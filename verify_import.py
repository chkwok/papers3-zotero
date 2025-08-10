#!/usr/bin/env python3
"""
Verify the Zotero database after import
"""

import sqlite3
import sys
from pathlib import Path

def verify_database(db_path='zotero.sqlite'):
    """Check the contents of the Zotero database after import"""
    
    if not Path(db_path).exists():
        print(f"Error: Database {db_path} not found")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n=== Zotero Database Contents ===\n")
    
    # Count items (excluding attachments and notes)
    cursor.execute("SELECT COUNT(*) FROM items WHERE itemTypeID NOT IN (3, 1)")
    item_count = cursor.fetchone()[0]
    print(f"Items (publications): {item_count}")
    
    # Count attachments
    cursor.execute("SELECT COUNT(*) FROM items WHERE itemTypeID = 3")
    attachment_count = cursor.fetchone()[0]
    print(f"Attachments: {attachment_count}")
    
    # Count collections
    cursor.execute("SELECT COUNT(*) FROM collections")
    collection_count = cursor.fetchone()[0]
    print(f"Collections: {collection_count}")
    
    # Count creators
    cursor.execute("SELECT COUNT(*) FROM creators")
    creator_count = cursor.fetchone()[0]
    print(f"Creators (authors): {creator_count}")
    
    # Count tags
    cursor.execute("SELECT COUNT(*) FROM tags")
    tag_count = cursor.fetchone()[0]
    print(f"Tags: {tag_count}")
    
    # Sample some items
    print("\n=== Sample Items ===\n")
    cursor.execute("""
        SELECT i.itemID, it.typeName, 
               (SELECT value FROM itemDataValues WHERE valueID = 
                    (SELECT valueID FROM itemData WHERE itemID = i.itemID AND fieldID = 1)) as title
        FROM items i
        JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
        WHERE i.itemTypeID NOT IN (3, 1)
        LIMIT 5
    """)
    
    items = cursor.fetchall()
    for item_id, item_type, title in items:
        print(f"[{item_id}] {item_type}: {title[:60] if title else '(No title)'}...")
    
    # Show collection hierarchy
    print("\n=== Collection Hierarchy (top level) ===\n")
    cursor.execute("""
        SELECT collectionID, collectionName,
               (SELECT COUNT(*) FROM collections c2 WHERE c2.parentCollectionID = c1.collectionID) as child_count,
               (SELECT COUNT(*) FROM collectionItems WHERE collectionID = c1.collectionID) as item_count
        FROM collections c1
        WHERE parentCollectionID IS NULL
        ORDER BY collectionName
        LIMIT 10
    """)
    
    collections = cursor.fetchall()
    for coll_id, name, child_count, item_count in collections:
        print(f"📁 {name} ({child_count} subfolders, {item_count} items)")
    
    # Check for items with tags
    print("\n=== Tag Usage ===\n")
    cursor.execute("""
        SELECT t.name, COUNT(it.itemID) as usage_count
        FROM tags t
        JOIN itemTags it ON t.tagID = it.tagID
        GROUP BY t.tagID
        ORDER BY usage_count DESC
        LIMIT 10
    """)
    
    tags = cursor.fetchall()
    for tag_name, usage_count in tags:
        print(f"🏷️  {tag_name}: used {usage_count} times")
    
    # Check for items in collections
    cursor.execute("""
        SELECT COUNT(DISTINCT itemID) FROM collectionItems
    """)
    items_in_collections = cursor.fetchone()[0]
    print(f"\n{items_in_collections} items are organized in collections")
    
    # Check Extra field for Papers3 metadata
    print("\n=== Papers3 Metadata in Extra Field ===\n")
    cursor.execute("""
        SELECT COUNT(*) FROM itemData id
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        WHERE id.fieldID = 16 AND idv.value LIKE '%Papers3 UUID:%'
    """)
    papers3_items = cursor.fetchone()[0]
    print(f"Items with Papers3 UUID preserved: {papers3_items}")
    
    # Sample an item with full metadata
    print("\n=== Sample Item Detail ===\n")
    cursor.execute("""
        SELECT i.itemID FROM items i
        WHERE i.itemTypeID NOT IN (3, 1)
        LIMIT 1
    """)
    sample_id = cursor.fetchone()
    
    if sample_id:
        item_id = sample_id[0]
        
        # Get all fields for this item
        cursor.execute("""
            SELECT f.fieldName, idv.value
            FROM itemData id
            JOIN fields f ON id.fieldID = f.fieldID
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.itemID = ?
        """, (item_id,))
        
        fields = cursor.fetchall()
        print(f"Item #{item_id} fields:")
        for field_name, value in fields:
            if len(str(value)) > 100:
                print(f"  {field_name}: {str(value)[:100]}...")
            else:
                print(f"  {field_name}: {value}")
        
        # Get creators for this item
        cursor.execute("""
            SELECT c.firstName, c.lastName, ct.creatorType, ic.orderIndex
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
        """, (item_id,))
        
        creators = cursor.fetchall()
        if creators:
            print(f"\n  Creators:")
            for first, last, creator_type, order in creators:
                print(f"    [{order}] {first} {last} ({creator_type})")
    
    conn.close()
    print("\n✅ Database verification complete")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Verify Zotero database after Papers3 import')
    parser.add_argument('--db', default='zotero.sqlite', help='Path to Zotero database')
    args = parser.parse_args()
    
    verify_database(args.db)